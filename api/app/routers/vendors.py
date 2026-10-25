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

logger = logging.getLogger(__name__)
router = APIRouter()


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
        vendor = Vendor(
            name=data['name'],
            company_name=data['company_name'],
            contact_person=data['contact_person'],
            phone=data['phone'],
            email=data.get('email'),
            address=data['address'],
            cnic=data.get('cnic'),
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
        last_entry = (
            db.query(VendorLedger)
            .filter_by(vendor_id=vendor_id)
            .order_by(VendorLedger.date.desc(), VendorLedger.id.desc())
            .first()
        )
        last_balance = float(last_entry.balance) if last_entry else 0.0
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
def add_purchase_order(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Add a new purchase order / consignment record"""
    try:
        data = body
        if not data:
            return _json({'error': 'No data provided'}, 400)
        required_fields = ['vendor_id', 'date', 'invoice_no', 'item_name', 'quantity', 'rate']
        for field in required_fields:
            if not data.get(field):
                return _json({'error': f'{field} is required'}, 400)
        vendor = db.get(Vendor, data['vendor_id'])
        if not vendor:
            return _json({'error': 'Vendor not found'}, 404)
        try:
            po_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return _json({'error': 'Invalid date format. Use YYYY-MM-DD'}, 400)
        quantity = int(data['quantity'])
        rate = float(data['rate'])
        amount = quantity * rate
        po = PurchaseOrder(
            vendor_id=data['vendor_id'],
            date=po_date,
            invoice_no=data['invoice_no'],
            item_name=data['item_name'],
            quantity=quantity,
            rate=rate,
            amount=amount,
            remarks=data.get('remarks'),
            status=data.get('status', 'ordered'),
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
def update_purchase_order_status(po_id: int, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Update purchase order status"""
    try:
        po = db.get(PurchaseOrder, po_id)
        if not po:
            return _json({'error': 'Purchase order not found'}, 404)
        data = body or {}
        new_status = data.get('status')
        if new_status not in ['ordered', 'in transit', 'received']:
            return _json({'error': 'Invalid status'}, 400)
        old_status = po.status
        po.status = new_status
        po.updated_at = datetime.utcnow()
        log_action(
            db, current_user, 'UPDATE_PO_STATUS', 'vendors', po.vendor_id,
            f"Updated Purchase Order {po.invoice_no} status from '{old_status}' to '{new_status}'",
        )
        db.commit()
        return _json({'message': 'Status updated successfully', 'status': po.status}, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating purchase order status: {e}")
        return _json({'error': 'Failed to update status'}, 500)
