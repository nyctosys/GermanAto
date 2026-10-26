"""FastAPI router ported from Flask. Preserves URL paths and JSON shapes."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Body
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.models import *  # noqa: F403,F401
from app.log_utils import log_action, save_uploaded_file
from app.search_suggestions import suggestions_for
from app.foundation.idempotent import idempotent_create
from app.foundation.overrides import user_has_permission
from app.foundation.validation import require_non_negative, require_positive_int
from app.procurement import (
    ProcurementError,
    create_supplier_invoice,
    known_rate_for_item,
    overdue_payables,
    post_credit_note,
    receive_goods,
    record_supplier_payment,
    vendor_outstanding,
)
from app.stock import PO_STATUSES

logger = logging.getLogger(__name__)
router = APIRouter()

_PO_STATUS_TRANSITIONS = {
    "draft": {"approved", "ordered", "closed"},
    "approved": {"ordered", "closed"},
    "ordered": {"partial", "received", "closed", "in transit"},
    "in transit": {"partial", "received", "closed"},
    "partial": {"partial", "received", "closed"},
    "received": {"closed"},
    "closed": set(),
}


def _can_override_po_price(db, user) -> bool:
    if not user:
        return False
    if getattr(user, "role", None) in ("admin", "owner", "accountant", "manager"):
        return True
    return user_has_permission(db, user, "override_po_price")


def _can_approve_po(db, user) -> bool:
    if not user:
        return False
    if getattr(user, "role", None) in ("admin", "owner", "accountant", "manager"):
        return True
    return user_has_permission(db, user, "approve_po")


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


# ===== VENDOR CRUD =====

@router.get('/api/vendors')
def get_vendors(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Get all vendors with optional search"""
    try:
        search_query = request.query_params.get('search', '').strip()
        query = db.query(Vendor)
        if search_query:
            query = query.filter(
                or_(
                    Vendor.name.ilike(f'%{search_query}%'),
                    Vendor.company_name.ilike(f'%{search_query}%'),
                    Vendor.contact_person.ilike(f'%{search_query}%'),
                    Vendor.phone.ilike(f'%{search_query}%'),
                    Vendor.email.ilike(f'%{search_query}%'),
                )
            )
        vendors = query.order_by(Vendor.created_at.desc()).all()
        rows = [vendor.to_dict() for vendor in vendors]
        payload = {'vendors': rows}
        if search_query and not rows:
            corpus = [row[0] for row in db.query(Vendor.name).distinct().all()]
            corpus += [row[0] for row in db.query(Vendor.company_name).distinct().all()]
            payload.update(suggestions_for(search_query, corpus))
        return _json(payload, 200)
    except Exception as e:
        logger.error(f"Error fetching vendors: {e}")
        return _json({'error': 'Failed to fetch vendors'}, 500)


@router.post('/api/vendors')
def create_vendor(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Create a new vendor"""
    try:
        data = body
        if not data:
            return _json({'error': 'No data provided'}, 400)
        required_fields = ['name', 'company_name', 'contact_person', 'phone', 'address']
        for field in required_fields:
            if not data.get(field):
                return _json({'error': f'{field} is required'}, 400)
        existing_vendor = db.query(Vendor).filter_by(
            name=data['name'],
            company_name=data['company_name'],
            phone=data['phone'],
        ).first()
        if existing_vendor:
            return _json({
                'error': 'Vendor already exists',
                'details': (
                    f'A vendor with the same name ({data["name"]}), '
                    f'company ({data["company_name"]}), and phone ({data["phone"]}) already exists.'
                ),
                'existing_vendor_id': existing_vendor.id,
            }, 409)
        terms = data.get('payment_terms_days', 30)
        try:
            terms = int(terms)
        except (TypeError, ValueError):
            terms = 30
        vendor = Vendor(
            name=data['name'],
            company_name=data['company_name'],
            contact_person=data['contact_person'],
            phone=data['phone'],
            email=data.get('email'),
            address=data['address'],
            cnic=data.get('cnic'),
            payment_terms_days=max(0, terms),
            bank_details=data.get('bank_details'),
            notes=data.get('notes'),
        )
        db.add(vendor)
        db.flush()
        log_action(db, current_user, 'CREATE', 'vendors', vendor.id, f"Created vendor {vendor.name} ({vendor.company_name})")
        db.commit()
        logger.info(f"Vendor created successfully: ID {vendor.id}")
        return _json({'message': 'Vendor created successfully', 'vendor': vendor.to_dict()}, 201)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating vendor: {e}")
        return _json({'error': 'Failed to create vendor'}, 500)


@router.get('/api/vendors/{vendor_id:int}')
def get_vendor(vendor_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Get specific vendor by ID"""
    try:
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            return _json({'error': 'Vendor not found'}, 404)
        return _json(vendor.to_dict(), 200)
    except Exception as e:
        logger.error(f"Error fetching vendor {vendor_id}: {e}")
        return _json({'error': 'Failed to fetch vendor'}, 500)


@router.put('/api/vendors/{vendor_id:int}')
def update_vendor(vendor_id: int, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Update an existing vendor"""
    try:
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            return _json({'error': 'Vendor not found'}, 404)
        data = body
        if not data:
            return _json({'error': 'No data provided'}, 400)
        vendor.name = data.get('name', vendor.name)
        vendor.company_name = data.get('company_name', vendor.company_name)
        vendor.contact_person = data.get('contact_person', vendor.contact_person)
        vendor.phone = data.get('phone', vendor.phone)
        vendor.email = data.get('email', vendor.email)
        vendor.address = data.get('address', vendor.address)
        vendor.cnic = data.get('cnic', vendor.cnic)
        if 'payment_terms_days' in data and data.get('payment_terms_days') is not None:
            try:
                vendor.payment_terms_days = max(0, int(data['payment_terms_days']))
            except (TypeError, ValueError):
                return _json({'error': 'payment_terms_days must be an integer'}, 400)
        if 'bank_details' in data:
            vendor.bank_details = data.get('bank_details')
        if 'notes' in data:
            vendor.notes = data.get('notes')
        vendor.updated_at = datetime.utcnow()
        log_action(db, current_user, 'UPDATE', 'vendors', vendor.id, f"Updated vendor details for {vendor.name}")
        db.commit()
        logger.info(f"Vendor updated successfully: ID {vendor.id}")
        return _json({'message': 'Vendor updated successfully', 'vendor': vendor.to_dict()}, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating vendor {vendor_id}: {e}")
        return _json({'error': 'Failed to update vendor'}, 500)


@router.delete('/api/vendors/{vendor_id:int}')
def delete_vendor(vendor_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Delete a vendor"""
    try:
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            return _json({'error': 'Vendor not found'}, 404)
        log_action(db, current_user, 'DELETE', 'vendors', vendor_id, f"Deleted vendor ID {vendor_id} ({vendor.name})")
        db.delete(vendor)
        db.commit()
        logger.info(f"Vendor deleted successfully: ID {vendor_id}")
        return _json({'message': 'Vendor deleted successfully'}, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting vendor {vendor_id}: {e}")
        return _json({'error': 'Failed to delete vendor'}, 500)


# ===== VENDOR LEDGER =====

@router.get('/api/vendors/{vendor_id:int}/ledger')
def get_vendor_ledger(vendor_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Get ledger entries for a specific vendor"""
    try:
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            return _json({'error': 'Vendor not found'}, 404)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        query = db.query(VendorLedger).filter_by(vendor_id=vendor_id)
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(VendorLedger.date >= start_date_obj)
            except ValueError:
                return _json({'error': 'Invalid start_date format. Use YYYY-MM-DD'}, 400)
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(VendorLedger.date <= end_date_obj)
            except ValueError:
                return _json({'error': 'Invalid end_date format. Use YYYY-MM-DD'}, 400)
        ledger_entries = query.order_by(VendorLedger.date.desc(), VendorLedger.id.desc()).all()
        return _json([entry.to_dict() for entry in ledger_entries], 200)
    except Exception as e:
        logger.error(f"Error fetching vendor ledger {vendor_id}: {e}")
        return _json({'error': 'Failed to fetch vendor ledger'}, 500)


@router.post('/api/ledger/add')
async def add_ledger_entry(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Add a new ledger entry (JSON or multipart with optional attachment)"""
    try:
        data = {}
        attachment_file = None
        ct = request.headers.get('content-type') or ''
        if 'multipart/form-data' in ct:
            form = await request.form()
            data = {k: v for k, v in form.items() if not hasattr(v, 'filename')}
            attachment = form.get('attachment')
            if attachment is not None and getattr(attachment, 'filename', None):
                attachment_file = attachment
        else:
            try:
                data = await request.json()
            except Exception:
                data = None
        if not data:
            return _json({'error': 'No data provided'}, 400)
        # Accept entry_type + amount (UI) or explicit debit/credit
        if data.get('entry_type') in ('debit', 'credit') and data.get('amount') is not None:
            try:
                amt = float(data['amount'])
            except (TypeError, ValueError):
                return _json({'error': 'Invalid amount'}, 400)
            if data['entry_type'] == 'debit':
                data['debit'], data['credit'] = amt, 0.0
            else:
                data['debit'], data['credit'] = 0.0, amt
        required_fields = ['vendor_id', 'date', 'description', 'debit', 'credit']
        for field in required_fields:
            if field not in data or data.get(field) is None:
                return _json({'error': f'{field} is required'}, 400)
        try:
            vendor_id = int(data['vendor_id'])
        except (ValueError, TypeError):
            return _json({'error': 'Invalid vendor_id'}, 400)
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            return _json({'error': 'Vendor not found'}, 404)
        try:
            entry_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return _json({'error': 'Invalid date format. Use YYYY-MM-DD'}, 400)
        debit = float(data['debit']) if data['debit'] else 0.0
        credit = float(data['credit']) if data['credit'] else 0.0
        last_balance = float(vendor_outstanding(db, vendor_id))
        new_balance = last_balance + debit - credit
        attachment_path = save_uploaded_file(attachment_file) if attachment_file else None
        ledger_entry = VendorLedger(
            vendor_id=vendor_id,
            date=entry_date,
            description=data['description'],
            folio=data.get('folio'),
            debit=debit,
            credit=credit,
            balance=new_balance,
            created_by_user=current_user.username if current_user else None,
            payment_notes=data.get('payment_notes'),
            attachment_path=attachment_path,
        )
        db.add(ledger_entry)
        log_action(
            db, current_user, 'CREATE_LEDGER', 'vendors', vendor_id,
            f"Added ledger entry: {data['description']} (Debit: {debit:.2f}, Credit: {credit:.2f})",
        )
        db.commit()
        logger.info(f"Ledger entry created successfully for vendor {vendor_id}")
        return _json({'message': 'Ledger entry added successfully', 'entry': ledger_entry.to_dict()}, 201)
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding ledger entry: {e}")
        return _json({'error': 'Failed to add ledger entry'}, 500)


@router.delete('/api/ledger/{ledger_id:int}')
def delete_ledger_entry(ledger_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Delete a ledger entry"""
    try:
        ledger_entry = db.get(VendorLedger, ledger_id)
        if not ledger_entry:
            return _json({'error': 'Ledger entry not found'}, 404)
        vendor_id = ledger_entry.vendor_id
        log_action(
            db, current_user, 'DELETE_LEDGER', 'vendors', vendor_id,
            f"Deleted ledger entry ID {ledger_id} ({ledger_entry.description})",
        )
        db.delete(ledger_entry)
        db.commit()
        logger.info(f"Ledger entry {ledger_id} deleted successfully")
        return _json({'message': 'Ledger entry deleted successfully'}, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting ledger entry: {e}")
        return _json({'error': 'Failed to delete ledger entry'}, 500)


# ===== PURCHASE ORDERS / CONSIGNMENTS =====

@router.get('/api/vendors/{vendor_id:int}/purchase-orders')
@router.get('/api/vendors/{vendor_id:int}/consignments')
def get_vendor_purchase_orders(vendor_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Get purchase order / consignment records for a vendor"""
    try:
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            return _json({'error': 'Vendor not found'}, 404)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        invoice_no = request.query_params.get('invoice_no')
        status = request.query_params.get('status')
        query = db.query(PurchaseOrder).filter_by(vendor_id=vendor_id)
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(PurchaseOrder.date >= start_date_obj)
            except ValueError:
                return _json({'error': 'Invalid start_date format. Use YYYY-MM-DD'}, 400)
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(PurchaseOrder.date <= end_date_obj)
            except ValueError:
                return _json({'error': 'Invalid end_date format. Use YYYY-MM-DD'}, 400)
        if invoice_no:
            query = query.filter(PurchaseOrder.invoice_no.ilike(f'%{invoice_no}%'))
        if status:
            query = query.filter(PurchaseOrder.status == status)
        purchase_orders = query.order_by(PurchaseOrder.date.desc(), PurchaseOrder.id.desc()).all()
        return _json([po.to_dict() for po in purchase_orders], 200)
    except Exception as e:
        logger.error(f"Error fetching vendor purchase orders {vendor_id}: {e}")
        return _json({'error': 'Failed to fetch purchase orders'}, 500)


@router.post('/api/purchase-orders/add')
@router.post('/api/consignments/add')
@idempotent_create
def add_purchase_order(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Add a new purchase order (default status: draft)."""
    try:
        data = body
        if not data:
            return _json({'error': 'No data provided'}, 400)
        # Accept legacy UI fields (description/amount) as aliases.
        if not data.get('item_name') and data.get('description'):
            data['item_name'] = data['description']
        if data.get('rate') is None and data.get('amount') is not None and data.get('quantity'):
            try:
                qty = int(data['quantity'])
                data['rate'] = float(data['amount']) / qty if qty else 0
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        if not data.get('invoice_no'):
            data['invoice_no'] = f"PO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        if not data.get('date'):
            data['date'] = datetime.utcnow().strftime('%Y-%m-%d')
        if not data.get('quantity'):
            data['quantity'] = 1
        required_fields = ['vendor_id', 'date', 'invoice_no', 'item_name', 'quantity', 'rate']
        for field in required_fields:
            if data.get(field) in (None, ''):
                return _json({'error': f'{field} is required'}, 400)
        vendor = db.get(Vendor, data['vendor_id'])
        if not vendor:
            return _json({'error': 'Vendor not found'}, 404)
        inventory_id = data.get('inventory_id')
        inv = None
        if inventory_id:
            inv = db.get(Inventory, inventory_id)
            if not inv:
                return _json({'error': 'Inventory item not found'}, 404)
            if not data.get('item_name'):
                data['item_name'] = inv.name
        try:
            po_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return _json({'error': 'Invalid date format. Use YYYY-MM-DD'}, 400)
        expected_delivery = None
        if data.get('expected_delivery'):
            try:
                expected_delivery = datetime.strptime(data['expected_delivery'], '%Y-%m-%d').date()
            except ValueError:
                return _json({'error': 'Invalid expected_delivery format. Use YYYY-MM-DD'}, 400)
        try:
            quantity = require_positive_int('quantity', data['quantity'])
            if data.get('rate') in (None, '') and inv is not None:
                data['rate'] = float(known_rate_for_item(db, vendor_id=int(data['vendor_id']), item=inv))
            rate = require_non_negative('rate', data['rate'])
        except ValueError as exc:
            return _json({'error': str(exc)}, 400)
        known = known_rate_for_item(db, vendor_id=int(data['vendor_id']), item=inv) if inv else None
        if known is not None and float(known) > 0 and abs(float(rate) - float(known)) > 0.009:
            if not _can_override_po_price(db, current_user):
                return _json(
                    {
                        'error': 'Price differs from known supplier/avg cost; override_po_price required',
                        'known_rate': float(known),
                        'requested_rate': float(rate),
                    },
                    403,
                )
        amount = quantity * rate
        status = (data.get('status') or 'draft').strip().lower()
        if status not in PO_STATUSES and status != 'in transit':
            status = 'draft'
        unit = data.get('unit') or (getattr(inv, 'unit', None) if inv else None) or 'pcs'
        po = PurchaseOrder(
            vendor_id=data['vendor_id'],
            inventory_id=inventory_id,
            date=po_date,
            expected_delivery=expected_delivery,
            invoice_no=data['invoice_no'],
            item_name=data['item_name'],
            unit=unit,
            quantity=quantity,
            qty_received=0,
            rate=rate,
            amount=amount,
            remarks=data.get('remarks'),
            status=status,
            created_by_user=current_user.username if current_user else None,
        )
        db.add(po)
        db.flush()
        log_action(
            db, current_user, 'CREATE_PO', 'vendors', po.vendor_id,
            f"Created Purchase Order {po.invoice_no}: {po.item_name} x{po.quantity} ({po.status})",
        )
        db.commit()
        logger.info(f"Purchase order record created successfully for vendor {data['vendor_id']}")
        return _json({
            'message': 'Purchase order record added successfully',
            'consignment': po.to_dict(),
            'purchase_order': po.to_dict(),
        }, 201)
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding purchase order: {e}")
        return _json({'error': 'Failed to add purchase order record'}, 500)


@router.delete('/api/purchase-orders/{po_id:int}')
@router.delete('/api/consignments/{consignment_id:int}')
def delete_purchase_order(
    request: Request,
    db: Session = Depends(get_db),
    po_id: int | None = None,
    consignment_id: int | None = None,
    current_user=Depends(require_roles(['admin', 'accountant'])),
):
    """Delete a purchase order / consignment record"""
    try:
        target_id = po_id if po_id is not None else consignment_id
        po = db.get(PurchaseOrder, target_id)
        if not po:
            return _json({'error': 'Purchase order record not found'}, 404)
        log_action(
            db, current_user, 'DELETE_PO', 'vendors', po.vendor_id,
            f"Deleted Purchase Order {po.invoice_no}: {po.item_name}",
        )
        db.delete(po)
        db.commit()
        logger.info(f"Purchase order record deleted successfully: ID {target_id}")
        return _json({'message': 'Purchase order record deleted successfully'}, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting purchase order: {e}")
        return _json({'error': 'Failed to delete purchase order record'}, 500)


@router.put('/api/purchase-orders/{po_id:int}/status')
def update_purchase_order_status(po_id: int, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Update purchase order status (draft → approved → ordered → … → closed). Receiving uses /receive."""
    try:
        po = db.get(PurchaseOrder, po_id)
        if not po:
            return _json({'error': 'Purchase order not found'}, 404)
        data = body or {}
        new_status = (data.get('status') or '').strip().lower()
        allowed = set(PO_STATUSES) | {'in transit'}
        if new_status not in allowed:
            return _json({'error': f'Invalid status. Allowed: {sorted(allowed)}'}, 400)
        if new_status in ('partial', 'received'):
            return _json(
                {
                    'error': 'Use POST /api/purchase-orders/{id}/receive for GRN; '
                    'status partial/received is set from qty received',
                },
                400,
            )
        old_status = (po.status or 'draft').strip().lower()
        allowed_next = _PO_STATUS_TRANSITIONS.get(old_status, set())
        if new_status != old_status and new_status not in allowed_next:
            return _json(
                {
                    'error': f'Cannot transition from {old_status} to {new_status}',
                    'allowed': sorted(allowed_next),
                },
                400,
            )
        if new_status == 'approved' and not _can_approve_po(db, current_user):
            return _json({'error': 'approve_po permission required'}, 403)
        if new_status == 'ordered' and old_status == 'draft' and not _can_approve_po(db, current_user):
            return _json(
                {'error': 'Draft POs require approval (or approve_po) before ordering'},
                403,
            )
        po.status = new_status
        if new_status == 'approved':
            po.approved_at = datetime.utcnow()
            po.approved_by_user = current_user.username if current_user else None
        po.updated_at = datetime.utcnow()
        log_action(
            db, current_user, 'UPDATE_PO_STATUS', 'vendors', po.vendor_id,
            f"Updated Purchase Order {po.invoice_no} status from '{old_status}' to '{new_status}'",
        )
        db.commit()
        return _json({'message': 'Status updated successfully', 'status': po.status, 'purchase_order': po.to_dict()}, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating purchase order status: {e}")
        return _json({'error': 'Failed to update status'}, 500)


@router.post('/api/purchase-orders/{po_id:int}/approve')
def approve_purchase_order(
    po_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager', 'manager'])),
):
    if not _can_approve_po(db, current_user):
        return _json({'error': 'approve_po permission required'}, 403)
    po = db.get(PurchaseOrder, po_id)
    if not po:
        return _json({'error': 'Purchase order not found'}, 404)
    if (po.status or '').lower() != 'draft':
        return _json({'error': f'Only draft POs can be approved (current: {po.status})'}, 400)
    po.status = 'approved'
    po.approved_at = datetime.utcnow()
    po.approved_by_user = current_user.username if current_user else None
    po.updated_at = datetime.utcnow()
    log_action(
        db, current_user, 'APPROVE_PO', 'vendors', po.vendor_id,
        f"Approved PO {po.document_no or po.id}",
    )
    db.commit()
    return _json({'message': 'PO approved', 'purchase_order': po.to_dict()}, 200)


@router.post('/api/purchase-orders/{po_id:int}/receive')
@idempotent_create
async def receive_purchase_order(
    po_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager'])),
):
    """Partial/full GRN. Updates stock + avg_cost via GoodsReceipt. Does NOT create payable."""
    try:
        po = db.get(PurchaseOrder, po_id)
        if not po:
            return _json({'error': 'Purchase order not found'}, 404)
        if (po.status or '').lower() in ('draft', 'closed'):
            return _json({'error': f'Cannot receive PO in status {po.status}'}, 400)

        content_type = (request.headers.get('content-type') or '').lower()
        receipt_path = po.receipt_attachment_path
        data: dict = {}
        if 'multipart/form-data' in content_type:
            form = await request.form()
            data = {k: form.get(k) for k in form.keys() if k != 'receipt'}
            upload = form.get('receipt') or form.get('attachment') or form.get('file')
            if upload is not None and hasattr(upload, 'filename') and upload.filename:
                receipt_path = save_uploaded_file(upload)
        else:
            data = await request.json()
            if data.get('receipt_attachment_path'):
                receipt_path = data['receipt_attachment_path']

        remaining = int(po.quantity or 0) - int(po.qty_received or 0)
        try:
            qty = require_positive_int('quantity', data.get('quantity', remaining))
        except ValueError as exc:
            return _json({'error': str(exc)}, 400)

        unit_cost = data.get('unit_cost', data.get('rate', po.rate))
        try:
            unit_cost = require_non_negative('unit_cost', unit_cost)
        except ValueError as exc:
            return _json({'error': str(exc)}, 400)

        known = float(po.rate or 0)
        if known > 0 and abs(float(unit_cost) - known) > 0.009:
            if not _can_override_po_price(db, current_user):
                return _json(
                    {
                        'error': 'Receive unit_cost differs from PO rate; override_po_price required',
                        'po_rate': known,
                        'unit_cost': float(unit_cost),
                    },
                    403,
                )

        inventory_id = data.get('inventory_id') or po.inventory_id
        if not inventory_id:
            return _json({'error': 'inventory_id is required to receive into stock'}, 400)
        item = db.get(Inventory, int(inventory_id))
        if not item:
            return _json({'error': 'Inventory item not found'}, 404)

        verified = data.get('verified_qty', qty)
        try:
            grn, txn = receive_goods(
                db,
                po=po,
                qty=qty,
                unit_cost=unit_cost,
                item=item,
                verified_qty=int(verified),
                receipt_path=receipt_path,
                notes=data.get('notes'),
                username=current_user.username if current_user else None,
                user_id=current_user.id if current_user else None,
            )
        except ProcurementError as exc:
            return _json({'error': str(exc)}, 400)

        log_action(
            db,
            current_user,
            'PO_RECEIVE',
            'vendors',
            po.vendor_id,
            f"GRN {grn.document_no} PO {po.invoice_no}: {item.part_number} x{qty} @ {unit_cost} → {po.status}",
        )
        db.commit()
        db.refresh(po)
        db.refresh(item)
        return _json(
            {
                'message': 'Goods received (no payable — record supplier invoice separately)',
                'purchase_order': po.to_dict(),
                'goods_receipt': grn.to_dict(),
                'inventory': {
                    'id': item.id,
                    'quantity': item.quantity,
                    'reserved': item.reserved,
                    'available': item.available,
                    'avg_cost': float(item.avg_cost or 0),
                },
                'movement': txn.to_dict(),
            },
            200,
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error receiving purchase order {po_id}: {e}")
        return _json({'error': f'Failed to receive purchase order: {e}'}, 500)


@router.get('/api/quotes/{quote_id:int}/shortages')
def quote_shortages(
    quote_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager', 'manager', 'service_advisor'])),
):
    from app.po_receive import shortage_lines

    return _json({'quote_id': quote_id, 'shortages': shortage_lines(db, quote_id)})


@router.post('/api/quotes/{quote_id:int}/create-pos-from-shortages')
@idempotent_create
def create_pos_from_shortages(
    quote_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager', 'manager'])),
):
    """Draft POs for shortage lines (requires vendor_id)."""
    from datetime import date
    from decimal import Decimal
    from app.po_receive import shortage_lines

    data = body or {}
    vendor_id = data.get('vendor_id')
    if not vendor_id:
        return _json({'error': 'vendor_id is required'}, 400)
    vendor = db.get(Vendor, int(vendor_id))
    if not vendor:
        return _json({'error': 'Vendor not found'}, 404)
    expected_delivery = None
    if data.get('expected_delivery'):
        try:
            expected_delivery = datetime.strptime(data['expected_delivery'], '%Y-%m-%d').date()
        except ValueError:
            return _json({'error': 'Invalid expected_delivery'}, 400)
    status = (data.get('status') or 'draft').strip().lower()
    if status not in ('draft', 'approved', 'ordered'):
        status = 'draft'
    created = []
    for line in shortage_lines(db, quote_id):
        qty = int(line['shortage'])
        inv = db.get(Inventory, line['inventory_id'])
        rate = known_rate_for_item(db, vendor_id=int(vendor_id), item=inv)
        if line.get('rate'):
            rate = Decimal(str(line['rate']))
        po = PurchaseOrder(
            vendor_id=int(vendor_id),
            date=date.today(),
            expected_delivery=expected_delivery,
            invoice_no=f"PO-Q{quote_id}-{line['inventory_id']}",
            item_name=line['item_name'],
            unit=getattr(inv, 'unit', None) if inv else 'pcs',
            quantity=qty,
            rate=rate,
            amount=(rate * qty).quantize(Decimal('0.01')),
            remarks=f"Shortage from quote #{quote_id}",
            status=status,
            inventory_id=line['inventory_id'],
            qty_received=0,
            quote_invoice_id=quote_id,
            created_by_user=getattr(current_user, 'username', None),
        )
        db.add(po)
        db.flush()
        created.append(po.to_dict())
    db.commit()
    return _json({'created': created}, 201)


# ===== AP documents: GRN list, invoices, payments, credits, statement, overdue =====

@router.get('/api/vendors/{vendor_id:int}/summary')
def vendor_summary(
    vendor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant'])),
):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        return _json({'error': 'Vendor not found'}, 404)
    outstanding = float(vendor_outstanding(db, vendor_id))
    po_count = db.query(PurchaseOrder).filter_by(vendor_id=vendor_id).count()
    open_inv = (
        db.query(SupplierInvoice)
        .filter(
            SupplierInvoice.vendor_id == vendor_id,
            SupplierInvoice.status.in_(('open', 'partial')),
        )
        .count()
    )
    return _json(
        {
            'vendor': vendor.to_dict(),
            'outstanding_balance': outstanding,
            'purchase_order_count': po_count,
            'open_invoice_count': open_inv,
        }
    )


@router.get('/api/vendors/{vendor_id:int}/statement')
def vendor_statement(
    vendor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant'])),
):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        return _json({'error': 'Vendor not found'}, 404)
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    query = db.query(VendorLedger).filter_by(vendor_id=vendor_id)
    if start_date:
        try:
            query = query.filter(
                VendorLedger.date >= datetime.strptime(start_date, '%Y-%m-%d').date()
            )
        except ValueError:
            return _json({'error': 'Invalid start_date'}, 400)
    if end_date:
        try:
            query = query.filter(
                VendorLedger.date <= datetime.strptime(end_date, '%Y-%m-%d').date()
            )
        except ValueError:
            return _json({'error': 'Invalid end_date'}, 400)
    # Chronological for statement reading
    entries = query.order_by(VendorLedger.date.asc(), VendorLedger.id.asc()).all()
    total_debit = sum(float(e.debit or 0) for e in entries)
    total_credit = sum(float(e.credit or 0) for e in entries)
    closing = float(entries[-1].balance) if entries else 0.0
    return _json(
        {
            'vendor': vendor.to_dict(),
            'entries': [e.to_dict() for e in entries],
            'total_debit': total_debit,
            'total_credit': total_credit,
            'closing_balance': closing,
            'outstanding_balance': float(vendor_outstanding(db, vendor_id)),
        }
    )


@router.get('/api/vendors/{vendor_id:int}/goods-receipts')
def list_goods_receipts(
    vendor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager'])),
):
    if not db.get(Vendor, vendor_id):
        return _json({'error': 'Vendor not found'}, 404)
    rows = (
        db.query(GoodsReceipt)
        .filter_by(vendor_id=vendor_id)
        .order_by(GoodsReceipt.id.desc())
        .all()
    )
    return _json({'goods_receipts': [r.to_dict() for r in rows]})


@router.get('/api/vendors/{vendor_id:int}/supplier-invoices')
def list_supplier_invoices(
    vendor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant'])),
):
    if not db.get(Vendor, vendor_id):
        return _json({'error': 'Vendor not found'}, 404)
    rows = (
        db.query(SupplierInvoice)
        .filter_by(vendor_id=vendor_id)
        .order_by(SupplierInvoice.id.desc())
        .all()
    )
    return _json({'supplier_invoices': [r.to_dict() for r in rows]})


@router.post('/api/supplier-invoices')
@idempotent_create
def post_supplier_invoice(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(['admin', 'accountant'])),
):
    data = body or {}
    vendor_id = data.get('vendor_id')
    if not vendor_id:
        return _json({'error': 'vendor_id is required'}, 400)
    vendor = db.get(Vendor, int(vendor_id))
    if not vendor:
        return _json({'error': 'Vendor not found'}, 404)
    grn = None
    if data.get('goods_receipt_id'):
        grn = db.get(GoodsReceipt, int(data['goods_receipt_id']))
        if not grn or grn.vendor_id != vendor.id:
            return _json({'error': 'Goods receipt not found'}, 404)
    po = None
    if data.get('purchase_order_id'):
        po = db.get(PurchaseOrder, int(data['purchase_order_id']))
    amount = data.get('amount')
    if amount is None and grn is not None:
        amount = float(grn.amount)
    invoice_no = data.get('supplier_invoice_no') or data.get('invoice_no')
    if not invoice_no:
        return _json({'error': 'supplier_invoice_no is required'}, 400)
    inv_date = None
    if data.get('date'):
        try:
            inv_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return _json({'error': 'Invalid date'}, 400)
    due = None
    if data.get('due_date'):
        try:
            due = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
        except ValueError:
            return _json({'error': 'Invalid due_date'}, 400)
    try:
        inv = create_supplier_invoice(
            db,
            vendor=vendor,
            amount=amount,
            supplier_invoice_no=str(invoice_no),
            invoice_date=inv_date,
            due_date=due,
            purchase_order=po,
            goods_receipt=grn,
            notes=data.get('notes'),
            attachment_path=data.get('attachment_path'),
            username=current_user.username if current_user else None,
        )
    except ProcurementError as exc:
        return _json({'error': str(exc)}, 400)
    log_action(
        db, current_user, 'SUPPLIER_INVOICE', 'vendors', vendor.id,
        f"Invoice {inv.supplier_invoice_no} amount {inv.amount}",
    )
    db.commit()
    return _json({'message': 'Supplier invoice recorded', 'supplier_invoice': inv.to_dict()}, 201)


@router.post('/api/supplier-payments')
@idempotent_create
def post_supplier_payment(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(['admin', 'accountant'])),
):
    data = body or {}
    vendor_id = data.get('vendor_id')
    if not vendor_id:
        return _json({'error': 'vendor_id is required'}, 400)
    vendor = db.get(Vendor, int(vendor_id))
    if not vendor:
        return _json({'error': 'Vendor not found'}, 404)
    inv = None
    if data.get('supplier_invoice_id'):
        inv = db.get(SupplierInvoice, int(data['supplier_invoice_id']))
        if not inv or inv.vendor_id != vendor.id:
            return _json({'error': 'Supplier invoice not found'}, 404)
    pay_date = None
    if data.get('date'):
        try:
            pay_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return _json({'error': 'Invalid date'}, 400)
    try:
        pay = record_supplier_payment(
            db,
            vendor=vendor,
            amount=data.get('amount'),
            payment_date=pay_date,
            method=data.get('method'),
            reference=data.get('reference'),
            supplier_invoice=inv,
            notes=data.get('notes') or data.get('payment_notes'),
            attachment_path=data.get('attachment_path'),
            username=current_user.username if current_user else None,
        )
    except ProcurementError as exc:
        return _json({'error': str(exc)}, 400)
    log_action(
        db, current_user, 'SUPPLIER_PAYMENT', 'vendors', vendor.id,
        f"Payment {pay.document_no} amount {pay.amount}",
    )
    db.commit()
    return _json({'message': 'Supplier payment recorded', 'supplier_payment': pay.to_dict()}, 201)


@router.post('/api/supplier-credit-notes')
@idempotent_create
def post_supplier_credit_note(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager'])),
):
    data = body or {}
    vendor_id = data.get('vendor_id')
    if not vendor_id:
        return _json({'error': 'vendor_id is required'}, 400)
    vendor = db.get(Vendor, int(vendor_id))
    if not vendor:
        return _json({'error': 'Vendor not found'}, 404)
    grn = db.get(GoodsReceipt, int(data['goods_receipt_id'])) if data.get('goods_receipt_id') else None
    po = db.get(PurchaseOrder, int(data['purchase_order_id'])) if data.get('purchase_order_id') else None
    inv = db.get(SupplierInvoice, int(data['supplier_invoice_id'])) if data.get('supplier_invoice_id') else None
    item = db.get(Inventory, int(data['inventory_id'])) if data.get('inventory_id') else None
    amount = data.get('amount')
    if amount is None and data.get('quantity') is not None and data.get('unit_cost') is not None:
        amount = float(data['quantity']) * float(data['unit_cost'])
    try:
        note = post_credit_note(
            db,
            vendor=vendor,
            amount=amount,
            reason=data.get('reason') or 'Supplier return',
            quantity=int(data.get('quantity') or 0),
            unit_cost=data.get('unit_cost') or 0,
            refund_amount=data.get('refund_amount') or 0,
            purchase_order=po,
            goods_receipt=grn,
            supplier_invoice=inv,
            item=item,
            notes=data.get('notes'),
            username=current_user.username if current_user else None,
            user_id=current_user.id if current_user else None,
        )
    except ProcurementError as exc:
        return _json({'error': str(exc)}, 400)
    log_action(
        db, current_user, 'SUPPLIER_CREDIT', 'vendors', vendor.id,
        f"Credit note {note.document_no} amount {note.amount}",
    )
    db.commit()
    return _json({'message': 'Credit note posted', 'supplier_credit_note': note.to_dict()}, 201)


@router.get('/api/reports/overdue-payables')
def report_overdue_payables(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant', 'manager'])),
):
    rows = overdue_payables(db)
    return _json({'overdue': rows, 'count': len(rows)})


@router.get('/api/purchase-orders/known-rate')
def get_known_supplier_rate(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager'])),
):
    try:
        vendor_id = int(request.query_params.get('vendor_id') or 0)
        inventory_id = int(request.query_params.get('inventory_id') or 0)
    except (TypeError, ValueError):
        return _json({'error': 'vendor_id and inventory_id required'}, 400)
    item = db.get(Inventory, inventory_id) if inventory_id else None
    rate = known_rate_for_item(db, vendor_id=vendor_id, item=item) if vendor_id else 0
    return _json(
        {
            'vendor_id': vendor_id,
            'inventory_id': inventory_id,
            'known_rate': float(rate),
            'unit': getattr(item, 'unit', None) if item else None,
            'item_name': item.name if item else None,
        }
    )
