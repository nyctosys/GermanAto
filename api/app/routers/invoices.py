"""FastAPI router ported from Flask. Preserves URL paths and JSON shapes."""
from __future__ import annotations

import json
import logging
import os
import re as _re
from datetime import datetime, timedelta, date
from functools import wraps
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body, File, UploadFile, Form
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import desc, or_, and_, func, text, extract, cast, String
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.models import *  # noqa: F403,F401
from app.invoice_math import *
from app.log_utils import log_action, document_log_entries, save_uploaded_file
from app.petty_cash import wants_till, till_expenses, till_receipts
from app.period_lock import (
    guard_period, guard_both, body_date, record_date, check_period_editable, is_period_open,
)
from app.document_links import apply_links, resolve_customer, resolve_car
from app.search_suggestions import suggestions_for
from app.inventory_utils import find_inventory_item_by_name as _inv_find_by_name
from app.inventory_transaction_utils import (
    log_inventory_transaction, log_issue_out, log_received, log_adjustment, get_inventory_transactions,
)
from app.repair_order_inventory_utils import (
    deduct_inventory_quantity, process_repair_order_parts,
    handle_repair_order_edit_inventory, restore_inventory_for_deleted_repair_order,
    calculate_inventory_changes, find_inventory_item_by_part_number, find_inventory_item_by_name,
)
from app.payroll import preview as payroll_preview, run_payroll, compute_salary
from app.whatsapp_notifications import whatsapp_notifier
from app.foundation.idempotent import idempotent_create
from app.foundation.overrides import assert_discount_override, require_audit_reason
from app.foundation.versioning import bump_version, check_version, extract_version
from app.pipeline import assert_invoice_unlocked, assert_qc_before_invoice, discount_pct, lock_invoice

logger = logging.getLogger(__name__)
router = APIRouter()


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


def _get_or_404(db: Session, model, pk):
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import logging
import re
import json
from datetime import datetime, timedelta
from functools import wraps

# Configure logging
logger = logging.getLogger(__name__)


def calculate_totals(items, labours):
    """Calculate total from items and labours"""
    try:
        items_total = sum(float(item.get('price', 0)) * int(item.get('quantity', 0)) for item in items)
        labours_total = sum(float(labour.get('price', 0)) for labour in labours)
        return round(items_total + labours_total, 2)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating totals: {e}")
        return 0.0

# Inventory deduction functionality has been removed
# This function is kept for compatibility but does nothing
def update_inventory_quantities(items):
    """Inventory deduction has been disabled - this function does nothing"""
    logger.info("Inventory deduction is disabled - no inventory quantities will be updated")
    return True

def validate_phone_number(phone):
    """Validate / normalize PK mobile to E.164. Mutates nothing; returns bool."""
    from app.foundation.validation import normalize_pk_phone

    if not phone:
        return False
    try:
        normalize_pk_phone(phone)
        return True
    except ValueError:
        return False

def validate_invoice_data(data):
    """Validate invoice data"""
    from app.foundation.validation import normalize_pk_phone, normalize_reg_no, validate_money_fields

    errors = []
    
    # Customer and car fields are now optional - only validate if provided and not "N/A"
    customer_fields = ['customer_name', 'customer_address', 'customer_phone', 
                      'customer_reg_no', 'customer_made', 'customer_mileage']
    
    for field in customer_fields:
        value = data.get(field)
        # Field is optional, but if provided and not "N/A", it should be valid
        if value and value != "N/A" and not str(value).strip():
            errors.append(f"{field.replace('_', ' ').title()} must be a valid string if provided")
    
    # Validate phone number only if provided and not "N/A"
    phone = data.get('customer_phone')
    if phone and phone != "N/A":
        try:
            data['customer_phone'] = normalize_pk_phone(phone)
        except ValueError as exc:
            errors.append(str(exc))

    reg = data.get('customer_reg_no')
    if reg and reg != "N/A":
        try:
            data['customer_reg_no'] = normalize_reg_no(reg)
        except ValueError as exc:
            errors.append(str(exc))
    
    # Validate numeric fields
    errors.extend(validate_money_fields(data, ("advance", "discount", "tax_amount")))
    
    # Validate items and labours
    items = data.get('items', [])
    labours = data.get('labours', [])
    
    if not items and not labours:
        errors.append("At least one item or labour is required")
    
    # Validate items
    for i, item in enumerate(items):
        if not item.get('product_name') or not str(item.get('product_name')).strip():
            errors.append(f"Item {i+1}: Product name is required")
        item_errs = validate_money_fields(item, ("price",))
        for err in item_errs:
            errors.append(f"Item {i+1}: {err}")
        try:
            quantity = int(item.get('quantity', 0))
            if quantity <= 0:
                errors.append(f"Item {i+1}: Quantity must be greater than 0")
        except (ValueError, TypeError):
            errors.append(f"Item {i+1}: Quantity must be a valid number")
    
    # Validate labours
    for i, labour in enumerate(labours):
        if not labour.get('description') or not str(labour.get('description')).strip():
            errors.append(f"Labour {i+1}: Description is required")
        for err in validate_money_fields(labour, ("price",)):
            errors.append(f"Labour {i+1}: {err}")
    
    return errors

def assert_can_edit_invoice(db: Session, current_user, invoice_id: int) -> None:
    """Admins/accountants always; others cannot edit invoices older than 1 day."""
    if current_user.role in ('admin', 'accountant'):
        return
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if (invoice.type_of or "").lower() == "invoice" and invoice.created_at:
        if invoice.created_at < datetime.utcnow() - timedelta(days=1):
            raise HTTPException(status_code=403, detail="Cannot edit invoices older than 1 day")

@router.post('/add')
@idempotent_create
def create_invoice(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Create a new invoice"""
    try:
        data = body
        
        if not data:
            return _json({'error': 'No data provided'}, 400)
        
        # Validate input data
        validation_errors = validate_invoice_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)
        
        # Extract and clean data
        customer_name = str(data.get('customer_name')).strip()
        customer_address = str(data.get('customer_address')).strip()
        customer_phone = str(data.get('customer_phone')).strip()
        customer_reg_no = str(data.get('customer_reg_no')).strip()
        customer_made = str(data.get('customer_made')).strip()
        customer_mileage = str(data.get('customer_mileage')).strip()
        customer_vin = str(data.get('customer_vin', '')).strip() if data.get('customer_vin') else None
        customer_color = str(data.get('customer_color', '')).strip() if data.get('customer_color') else None
        customer_chasis = str(data.get('customer_chasis', '')).strip() if data.get('customer_chasis') else None
        advance = float(data.get('advance', 0))
        discount = float(data.get('discount', 0))
        type_of = str(data.get('type_of', 'invoice')).strip().lower()
        include_tax = bool(data.get('include_tax', False))
        tax_amount = float(data.get('tax_amount', 0))
        items_data = data.get('items', [])
        labours_data = data.get('labours', [])
        
        # Calculate totals
        total = calculate_totals(items_data, labours_data)
        
        # If tax is included, the net_total should be the base amount (without tax)
        # The total passed to the database should include tax if applicable
        if include_tax:
            net_total = total  # This is the base amount without tax
            total_with_tax = total + tax_amount
            balance = round(total_with_tax - discount - advance, 2)
        else:
            net_total = total
            balance = round(total - discount - advance, 2)

        assert_discount_override(
            db, current_user, discount_pct(discount, net_total), reason=data.get("reason")
        )

        repair_order_id = data.get("repair_order_id")
        if type_of == "invoice" and repair_order_id:
            assert_qc_before_invoice(db, int(repair_order_id))
        
        # Create invoice with transaction
        try:
            # Set appropriate default status based on document type
            default_status = 'unpaid' if type_of == 'invoice' else 'pending'
            
            invoice = Invoice(
                customer_name=customer_name,
                customer_address=customer_address,
                customer_phone=customer_phone,
                customer_reg_no=customer_reg_no,
                customer_made=customer_made,
                customer_mileage=customer_mileage,
                customer_vin=customer_vin,
                customer_color=customer_color,
                customer_chasis=customer_chasis,
                balance=balance,
                advance=advance,
                net_total=net_total,
                discount=discount,
                type_of=type_of,
                include_tax=include_tax,
                tax_amount=tax_amount,
                status=default_status,
                created_by_user=current_user.username if current_user else None,
                visit_id=data.get("visit_id"),
                job_card_id=data.get("job_card_id"),
                repair_order_id=int(repair_order_id) if repair_order_id else None,
            )
            invoice.status = calculate_invoice_status(invoice)
            if type_of == "invoice":
                lock_invoice(invoice)

            # Link the document to the customer and car it was written for, and
            # claim the car for that customer if it had no owner yet.
            apply_links(db, invoice, data)

            db.add(invoice)
            db.flush()  # Get the ID without committing
            
            # Add items
            for item in items_data:
                price = float(item['price'])
                proposed = float(item.get('proposed_price', price))
                invoice_item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_name=str(item['product_name']).strip(),
                    part_number=str(item.get('part_number', '')).strip() if item.get('part_number') else None,
                    quantity=int(item['quantity']),
                    price=price,
                    proposed_price=proposed,
                    inventory_id=item.get('inventory_id'),
                    job_card_line_id=item.get('job_card_line_id'),
                    approval_status=item.get('approval_status') or 'pending',
                )
                db.add(invoice_item)
            
            # Add labours
            for labour in labours_data:
                price = float(labour['price'])
                proposed = float(labour.get('proposed_price', price))
                invoice_labour = InvoiceLabour(
                    invoice_id=invoice.id,
                    description=str(labour['description']).strip(),
                    price=price,
                    proposed_price=proposed,
                    labour_code_id=labour.get('labour_code_id'),
                    std_hours=labour.get('std_hours'),
                    job_card_line_id=labour.get('job_card_line_id'),
                    approval_status=labour.get('approval_status') or 'pending',
                )
                db.add(invoice_labour)
            
            # Update inventory quantities only for invoices (not quotes)
            # DISABLED: Inventory is no longer deducted when creating invoices
            # if type_of == 'invoice' and items_data:
            #     try:
            #         update_inventory_quantities(items_data)
            #     except ValueError as e:
            #         db.rollback()
            #         return _json({'error': str(e)}, 400)
            #     except Exception as e:
            #         db.rollback()
            #         logger.error(f"Error updating inventory: {e}")
            #         return _json({'error': 'Failed to update inventory'}, 500)
            
            log_action(db, current_user, 'CREATE', 'invoices' if type_of == 'invoice' else 'quotes', invoice.id, f"Created {type_of} for customer {customer_name} total {invoice.net_total} PKR")
            db.commit()
            
            logger.info(f"Invoice created successfully: ID {invoice.id}")
            
            # Send WhatsApp notification to client
            try:
                # Prepare invoice data for notification
                invoice_data = {
                    'id': invoice.id,
                    'customer_name': customer_name,
                    'customer_phone': customer_phone,
                    'net_total': net_total,
                    'type_of': type_of
                }
                
                # Send WhatsApp notification
                notification_result = whatsapp_notifier.send_invoice_notification(invoice_data)
                
                # Log notification result
                if notification_result['success']:
                    logger.info(f"WhatsApp notification sent successfully for invoice {invoice.id}")
                    
                    # Save notification record to database
                    notification_record = WhatsAppNotification(
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        notification_type='invoice' if type_of == 'invoice' else 'quote',
                        message_content=whatsapp_notifier._create_invoice_message(customer_name, invoice.id, f"{float(net_total):,.2f} PKR") if type_of == 'invoice' else whatsapp_notifier._create_quote_message(customer_name, invoice.id, f"{float(net_total):,.2f} PKR"),
                        related_document_type='invoice',
                        related_document_id=invoice.id,
                        whatsapp_message_id=notification_result.get('message_id'),
                        status=notification_result.get('status', 'sent')
                    )
                    db.add(notification_record)
                    db.commit()
                    
                else:
                    logger.warning(f"WhatsApp notification failed for invoice {invoice.id}: {notification_result.get('error', 'Unknown error')}")
                    
                    # Save failed notification record
                    notification_record = WhatsAppNotification(
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        notification_type='invoice' if type_of == 'invoice' else 'quote',
                        message_content=whatsapp_notifier._create_invoice_message(customer_name, invoice.id, f"{float(net_total):,.2f} PKR") if type_of == 'invoice' else whatsapp_notifier._create_quote_message(customer_name, invoice.id, f"{float(net_total):,.2f} PKR"),
                        related_document_type='invoice',
                        related_document_id=invoice.id,
                        status='failed',
                        error_message=notification_result.get('error', 'Unknown error')
                    )
                    db.add(notification_record)
                    db.commit()
                    
            except Exception as e:
                logger.error(f"Error sending WhatsApp notification for invoice {invoice.id}: {e}")
                # Don't fail the invoice creation if notification fails
            
            return _json({
                'message': 'Invoice created successfully',
                'invoice_id': invoice.id,
                'customer_name': customer_name,
                'total': total,
                'balance': balance,
                'whatsapp_sent': notification_result.get('success', False) if 'notification_result' in locals() else False
            }, 201)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating invoice: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Unexpected error creating invoice: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/invoice/{invoice_id:int}')
def get_invoice(invoice_id, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get invoice by ID"""
    try:
        if not invoice_id or invoice_id <= 0:
            return _json({'error': 'Invalid invoice ID'}, 400)
        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            return _json({'error': 'Invoice not found'}, 404)
        invoice_data = {
            "id": invoice.id,
            "customer_name": invoice.customer_name,
            "customer_address": invoice.customer_address,
            "customer_phone": invoice.customer_phone,
            "customer_reg_no": invoice.customer_reg_no,
            "customer_made": invoice.customer_made,
            "customer_mileage": invoice.customer_mileage,
            "customer_vin": invoice.customer_vin,
            "customer_color": invoice.customer_color or "",
            "customer_chasis": invoice.customer_chasis or "",
            "customer_id": invoice.customer_id,
            "customer_code": f"CN{invoice.customer_id:03d}" if invoice.customer_id else "",
            "car_id": invoice.car_id,
            "created_at": invoice.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "balance": float(invoice.balance),
            "advance": float(invoice.advance),
            "net_total": float(invoice.net_total),
            "total": float(invoice.net_total),  # Return total for frontend compatibility
            "discount": float(invoice.discount),
            "type_of": invoice.type_of,
            "include_tax": invoice.include_tax,
            "tax_amount": float(invoice.tax_amount),
            "paid_amount": float(invoice.paid_amount or 0),
            "status": invoice.status,
            "created_by_user": invoice.created_by_user,
            "updated_by_user": invoice.updated_by_user,
            "updated_at": invoice.updated_at.strftime("%Y-%m-%d %H:%M:%S") if invoice.updated_at else None,
            "payments_history": json.loads(invoice.payments_history) if invoice.payments_history else [],
            "items": [
                {
                    "id": item.id, 
                    "product_name": item.product_name, 
                    "part_number": item.part_number,
                    "quantity": item.quantity, 
                    "price": float(item.price)
                }
                for item in invoice.items
            ],
            "labours": [
                {
                    "id": labour.id, 
                    "description": labour.description, 
                    "price": float(labour.price)
                }
                for labour in invoice.labours
            ]
        }
        
        # If color or chassis is not saved, try to fetch from Car table
        if not invoice_data["customer_color"] or not invoice_data["customer_chasis"]:
            car = None
            if invoice.customer_vin:
                car = db.query(Car).filter_by(vin=invoice.customer_vin).first()
            if not car and invoice.customer_reg_no:
                car = db.query(Car).filter_by(plate_no=invoice.customer_reg_no).first()
            if car:
                if not invoice_data["customer_color"]:
                    invoice_data["customer_color"] = car.color or ""
                if not invoice_data["customer_chasis"]:
                    invoice_data["customer_chasis"] = car.chasis_no or ""
        
        return _json(invoice_data, 200)
    except Exception as e:
        logger.error(f"Error getting invoice {invoice_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.delete('/invoice/{invoice_id:int}/delete')
def delete_invoice(invoice_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Delete invoice by ID"""
    try:
        if not invoice_id or invoice_id <= 0:
            return _json({'error': 'Invalid invoice ID'}, 400)
        
        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            return _json({'error': 'Invoice not found'}, 404)
        assert_invoice_unlocked(invoice)
        require_audit_reason(kind="delete")
        
        try:
            # Soft-delete via session hooks (hard cascade on children avoided)
            log_action(db, current_user, 'DELETE', 'invoices' if invoice.type_of == 'invoice' else 'quotes', invoice_id, f"Deleted {invoice.type_of} ID {invoice_id} for customer {invoice.customer_name}")
            db.delete(invoice)
            db.commit()
            
            logger.info(f"Invoice deleted successfully: ID {invoice_id}")
            
            return _json({'message': 'Invoice deleted successfully'}, 200)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting invoice {invoice_id}: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Error deleting invoice {invoice_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.put('/invoice/{invoice_id:int}/update')
def update_invoice(invoice_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(get_current_user)):
    """Update invoice by ID"""
    try:
        if not invoice_id or invoice_id <= 0:
            return _json({'error': 'Invalid invoice ID'}, 400)

        assert_can_edit_invoice(db, current_user, invoice_id)

        data = body
        if not data:
            return _json({'error': 'No data provided'}, 400)
        
        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            return _json({'error': 'Invoice not found'}, 404)
        assert_invoice_unlocked(invoice)
        check_version(invoice, extract_version(data))
        
        # Validate input data
        validation_errors = validate_invoice_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)

        new_discount = float(data['discount']) if 'discount' in data else float(invoice.discount or 0)
        items_preview = data.get('items', [{'price': i.price, 'quantity': i.quantity} for i in (invoice.items or [])])
        labours_preview = data.get('labours', [{'price': l.price} for l in (invoice.labours or [])])
        preview_total = calculate_totals(items_preview, labours_preview)
        assert_discount_override(
            db, current_user, discount_pct(new_discount, preview_total), reason=data.get("reason")
        )
        
        try:
            # Update invoice basic fields
            if 'customer_name' in data:
                invoice.customer_name = str(data['customer_name']).strip()
            if 'customer_address' in data:
                invoice.customer_address = str(data['customer_address']).strip()
            if 'customer_phone' in data:
                invoice.customer_phone = str(data['customer_phone']).strip()
            if 'customer_reg_no' in data:
                invoice.customer_reg_no = str(data['customer_reg_no']).strip()
            if 'customer_made' in data:
                invoice.customer_made = str(data['customer_made']).strip()
            if 'customer_mileage' in data:
                invoice.customer_mileage = str(data['customer_mileage']).strip()
            if 'customer_vin' in data:
                invoice.customer_vin = str(data['customer_vin']).strip() if data['customer_vin'] else None
            if 'customer_color' in data:
                invoice.customer_color = str(data['customer_color']).strip() if data['customer_color'] else None
            if 'customer_chasis' in data:
                invoice.customer_chasis = str(data['customer_chasis']).strip() if data['customer_chasis'] else None
            # Re-link on every save: an edit can move an invoice to a
            # different customer or car, and a car added mid-edit needs claiming.
            apply_links(db, invoice, data)

            if 'type_of' in data:
                invoice.type_of = str(data['type_of']).strip().lower()
            if 'advance' in data:
                invoice.advance = float(data['advance'])
            if 'discount' in data:
                invoice.discount = float(data['discount'])
            if 'include_tax' in data:
                invoice.include_tax = bool(data['include_tax'])
            if 'tax_amount' in data:
                invoice.tax_amount = float(data['tax_amount'])
            
            items_data = data.get('items', [])
            labours_data = data.get('labours', [])
            
            # Clear old items and labours to avoid stale session data
            invoice.items = []
            invoice.labours = []
            
            # Add new items
            for item in items_data:
                new_item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_name=str(item['product_name']).strip(),
                    part_number=str(item.get('part_number', '')).strip() if item.get('part_number') else None,
                    quantity=int(item['quantity']),
                    price=float(item['price'])
                )
                invoice.items.append(new_item)
            
            # Add new labours
            for labour in labours_data:
                new_labour = InvoiceLabour(
                    invoice_id=invoice.id,
                    description=str(labour['description']).strip(),
                    price=float(labour['price'])
                )
                invoice.labours.append(new_labour)
            
            # Recalculate total
            total = calculate_totals(items_data, labours_data)
            invoice.net_total = total
            
            # Calculate balance considering tax, discount, and already paid amount
            current_paid = float(invoice.paid_amount or 0)
            if invoice.include_tax and invoice.tax_amount > 0:
                total_with_tax = total + invoice.tax_amount
                invoice.balance = round(total_with_tax - invoice.discount - invoice.advance - current_paid, 2)
            else:
                invoice.balance = round(total - invoice.discount - invoice.advance - current_paid, 2)
            
            # Set updater and calculate status
            invoice.updated_by_user = current_user.username if current_user else None
            invoice.updated_at = datetime.utcnow()
            invoice.status = calculate_invoice_status(invoice)
            bump_version(invoice)
            
            log_action(db, current_user, 'UPDATE', 'invoices' if invoice.type_of == 'invoice' else 'quotes', invoice.id, f"Updated {invoice.type_of} details (Net Total: {invoice.net_total} PKR, Balance: {invoice.balance} PKR)")
            db.commit()
            
            logger.info(f"Invoice updated successfully: ID {invoice_id}")
            
            return _json({
                'message': 'Invoice updated successfully', 
                'invoice_id': invoice.id,
                'total': total,
                'balance': invoice.balance
            }, 200)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating invoice {invoice_id}: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Error updating invoice {invoice_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/search')
def search_invoices(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Search invoices by various criteria"""
    try:
        query = request.query_params.get('q', '').strip()
        search_id = request.query_params.get('id', '').strip()
        status = request.query_params.get('status', '').strip()
        type_of = request.query_params.get('type', '').strip()
        date_from = request.query_params.get('date_from', '').strip()
        date_to = request.query_params.get('date_to', '').strip()
        
        # If no search criteria provided, return empty results in proper format
        if not query and not search_id and not status and not type_of and not date_from and not date_to:
            return _json({
                'quotes': [],
                'invoices': []
            }, 200)
        
        # Sanitize query to prevent SQL injection
        if len(query) > 100:  # Limit query length
            return _json({'error': 'Search query too long'}, 400)
        
        # Build search conditions
        search_conditions = []
        
        # Add ID search if provided
        if search_id:
            try:
                query_id = int(search_id)
                search_conditions.append(Invoice.id == query_id)
            except ValueError:
                # Invalid ID format, ignore it
                pass
        
        # Add keyword search if provided
        if query:
            search_conditions.append(
                or_(
                    Invoice.customer_name.ilike(f'%{query}%'),
                    Invoice.customer_phone.ilike(f'%{query}%'),
                    Invoice.customer_reg_no.ilike(f'%{query}%'),
                    Invoice.type_of.ilike(f'%{query}%'),
                    cast(Invoice.id, String).ilike(f'%{query}%')
                )
            )
        
        # Add status filter if provided
        if status:
            # Normalize status: handle both "partially paid" and "partially_paid"
            # Check both formats since database might have either
            if status.lower() == 'partially paid':
                # Use OR condition to match both "partially paid" and "partially_paid"
                normalized_status = status.replace(' ', '_')
                search_conditions.append(or_(Invoice.status == normalized_status, Invoice.status == status))
            else:
                normalized_status = status
                search_conditions.append(Invoice.status == normalized_status)
        
        # Add type_of filter if provided
        if type_of:
            search_conditions.append(Invoice.type_of.ilike(type_of))
        
        # Add date range filter if provided
        if date_from:
            try:
                from datetime import datetime
                date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
                search_conditions.append(Invoice.created_at >= date_from_parsed)
            except ValueError:
                # Invalid date format, ignore it
                pass
        
        if date_to:
            try:
                from datetime import datetime, timedelta
                date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
                # Add 1 day to include the entire end date (up to 23:59:59)
                date_to_end = date_to_parsed + timedelta(days=1)
                search_conditions.append(Invoice.created_at < date_to_end)
            except ValueError:
                # Invalid date format, ignore it
                pass
        
        # If no valid search conditions, return empty results in proper format
        if not search_conditions:
            return _json({
                'quotes': [],
                'invoices': []
            }, 200)
        
        # Combine conditions with AND
        final_condition = and_(*search_conditions)
        
        # Execute search (no limit - return all matching results)
        results = db.query(Invoice).filter(final_condition).order_by(Invoice.created_at.desc()).all()
        
        invoice_list = []
        for invoice in results:
            invoice_data = {
                "id": invoice.id,
                "document_no": invoice.document_no,
                "customer_name": invoice.customer_name,
                "customer_phone": invoice.customer_phone,
                "customer_reg_no": invoice.customer_reg_no,
                "type_of": invoice.type_of,
                "created_at": invoice.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "balance": float(invoice.balance),
                "advance": float(invoice.advance),
                "total": float(invoice.net_total),
                "net_total": float(invoice.net_total),  # Return both for frontend compatibility
                "discount": float(invoice.discount),
                "include_tax": invoice.include_tax,
                "tax_amount": float(invoice.tax_amount),
                "paid_amount": float(invoice.paid_amount or 0),
                "status": invoice.status,
                "approval_state": getattr(invoice, "approval_state", None),
                "required_advance": float(getattr(invoice, "required_advance", None) or 0),
                "created_by_user": invoice.created_by_user,
                "updated_by_user": invoice.updated_by_user,
                "updated_at": invoice.updated_at.strftime("%Y-%m-%d %H:%M:%S") if invoice.updated_at else None,
                "payments_history": json.loads(invoice.payments_history) if invoice.payments_history else []
            }
            invoice_list.append(invoice_data)
        
        # Separate quotes and invoices
        quotes = [item for item in invoice_list if item['type_of'].lower() == 'quote']
        invoices = [item for item in invoice_list if item['type_of'].lower() == 'invoice']
        
        payload = {'quotes': quotes, 'invoices': invoices}

        # A keyword search that matched nothing: suggest a spelling and the
        # nearest customer names actually on file.
        if query and not invoice_list:
            corpus = [row[0] for row in db.query(Invoice.customer_name).distinct().all()]
            payload.update(suggestions_for(query, corpus))

        return _json(payload, 200)
        
    except Exception as e:
        logger.error(f"Error searching invoices: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/health')
def health_check(request: Request, db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection using text() for SQLAlchemy 2.0+
        db.execute(text('SELECT 1'))
        return _json({'status': 'healthy', 'database': 'connected'}, 200)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return _json({'status': 'unhealthy', 'error': str(e)}, 500)

@router.post('/invoice/{invoice_id:int}/convert')
def convert_quote_to_invoice(invoice_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Convert a quote to an invoice (in-place, same ID). Requires QC when linked to an RO."""
    try:
        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            return _json({'error': 'Invoice/Quote not found'}, 404)
        if invoice.type_of == 'invoice':
            return _json({'error': 'Already an invoice'}, 400)
        if invoice.is_variation:
            return _json({'error': 'Variation quotes cannot convert directly; fold approved lines into the RO invoice'}, 400)

        if invoice.repair_order_id:
            assert_qc_before_invoice(db, invoice.repair_order_id)

        # Only approved lines (or legacy pending-all) may bill
        for item in invoice.items or []:
            st = (item.approval_status or "pending").lower()
            if st == "rejected":
                continue
            if st not in ("approved", "pending"):
                return _json({'error': f'Line {item.id} not approved'}, 400)
        # Drop rejected lines from billing by zeroing qty (keep audit trail)
        for item in invoice.items or []:
            if (item.approval_status or "").lower() == "rejected":
                item.quantity = 0
        for labour in invoice.labours or []:
            if (labour.approval_status or "").lower() == "rejected":
                labour.price = 0.0

        invoice.type_of = 'invoice'
        invoice.status = 'unpaid'
        lock_invoice(invoice)

        db.commit()
        return _json({'message': 'Quote converted to invoice successfully', 'invoice_id': invoice.id}, 200)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"convert quote error: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.put('/invoice/{invoice_id:int}/status')
def update_invoice_status(invoice_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Manually updating status is disabled. This endpoint automatically calculates status."""
    try:
        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            return _json({'error': 'Invoice not found'}, 404)
        
        # Auto calculate status
        old_status = invoice.status
        invoice.status = calculate_invoice_status(invoice)
        db.commit()
        
        if old_status != invoice.status:
            log_action(db, current_user, 'UPDATE_STATUS', 'invoices', invoice.id, f"Auto-calculated status: updated from {old_status} to {invoice.status}")
            
        return _json({'message': 'Status auto-calculated', 'status': invoice.status}, 200)
    except Exception as e:
        logger.error(f"Error auto-updating invoice status {invoice_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/invoice/{invoice_id:int}/log')
def get_invoice_log(invoice_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """One invoice or quote's full history: what was done to it, and every
    payment against it.

    Serves quotes too - a quote is a row in the same table. It simply has no
    payments, because nothing is owed on one until it becomes an invoice.
    """
    try:
        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            return _json({'error': 'Invoice not found'}, 404)

        payments = []
        if invoice.payments_history:
            try:
                payments = json.loads(invoice.payments_history)
            except (ValueError, TypeError):
                payments = []

        return _json({
            'kind': (invoice.type_of or 'invoice').lower(),
            'document_id': invoice.id,
            'reference': f"#{invoice.id}",
            'customer_name': invoice.customer_name,
            'created_at': invoice.created_at.strftime('%Y-%m-%d %H:%M:%S') if invoice.created_at else '',
            'created_by': invoice.created_by_user,
            'advance': float(invoice.advance or 0),
            'amount_due': round(invoice_amount_due(invoice), 2),
            'amount_paid': round(invoice_amount_paid(invoice), 2),
            'amount_remaining': invoice_amount_remaining(invoice),
            'payments': payments,
            'entries': document_log_entries(db, 'invoice', invoice.id),
        }, 200)
    except Exception as e:
        logger.error(f"Error loading invoice log {invoice_id}: {e}")
        return _json({'error': 'Failed to load the log'}, 500)


@router.put('/invoice/{invoice_id:int}/update-balance')
@idempotent_create
async def update_invoice_balance(invoice_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Add to the paid amount and update status of an invoice (with optional proof upload).

    Honors Idempotency-Key so repeated payment submits do not double-apply.
    """
    try:
        paid_amount_str = None
        proof_file = None
        ct = request.headers.get('content-type') or ''
        if 'multipart/form-data' in ct:
            form = await request.form()
            paid_amount_str = form.get('paid_amount')
            proof = form.get('proof')
            if proof is not None and getattr(proof, 'filename', None):
                proof_file = proof
        else:
            try:
                data = await request.json()
            except Exception:
                data = None
            if data:
                paid_amount_str = data.get('paid_amount')

        if paid_amount_str is None:
            return _json({'error': 'No paid_amount provided'}, 400)
            
        try:
            additional_amount = float(paid_amount_str)
            # Zero used to be accepted, recording an empty payment (and its
            # proof) against the invoice for no money.
            if additional_amount <= 0:
                return _json({'error': 'Payment amount must be greater than zero.'}, 400)
        except (ValueError, TypeError):
            return _json({'error': 'Invalid paid_amount value'}, 400)
        
        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            return _json({'error': 'Invoice not found'}, 404)

        # Quotes are not owed yet, so they cannot take payments. The UI only
        # offers this on invoice cards, but the endpoint is reachable directly.
        if (invoice.type_of or '').lower() != 'invoice':
            return _json({
                'error': 'Payments can only be recorded against an invoice. '
                         'Convert this quote to an invoice first.'
            }, 400)

        # A payment may not exceed what is still owed. Checked before the proof
        # file is saved so a rejected payment leaves no orphaned upload.
        remaining = invoice_amount_remaining(invoice)
        if remaining <= 0:
            return _json({
                'error': 'This invoice is already fully paid.',
                'remaining': 0.0
            }, 400)
        if round(additional_amount, 2) > remaining:
            return _json({
                'error': (
                    f'Payment of {additional_amount:.2f} PKR exceeds the '
                    f'{remaining:.2f} PKR still owed on this invoice.'
                ),
                'remaining': remaining
            }, 400)

        # Save optional proof file
        proof_path = None
        if proof_file:
            proof_path = save_uploaded_file(proof_file)
            
        # Add to existing paid amount
        current_paid = invoice.paid_amount or 0
        invoice.paid_amount = current_paid + additional_amount
        
        # Calculate balance
        invoice.balance = invoice_amount_remaining(invoice)
        
        # Auto-calculate status
        invoice.status = calculate_invoice_status(invoice)
        invoice.updated_by_user = current_user.username if current_user else None
        invoice.updated_at = datetime.utcnow()
        
        # Record payment transaction in history
        history_list = []
        if invoice.payments_history:
            try:
                history_list = json.loads(invoice.payments_history)
            except Exception:
                history_list = []
                
        payment_record = {
            'amount': additional_amount,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'person': current_user.username if current_user else 'anonymous/system',
            'proof_path': proof_path
        }
        history_list.append(payment_record)
        invoice.payments_history = json.dumps(history_list)
        
        # Log action
        log_action(db, current_user, 'UPDATE_BALANCE', 'invoices', invoice.id, f"Added payment of {additional_amount:.2f} PKR. Total paid: {invoice.paid_amount:.2f} PKR. Balance: {invoice.balance:.2f} PKR")
        db.commit()
        
        return _json({
            'message': f'Added {additional_amount:.2f} PKR to paid amount. Total paid: {invoice.paid_amount:.2f} PKR',
            'paid_amount': invoice.paid_amount,
            'balance': invoice.balance,
            'status': invoice.status,
            'payments_history': history_list
        }, 200)
        
    except ValueError as e:
        return _json({'error': 'Invalid values'}, 400)
    except Exception as e:
        logger.error(f"Error updating invoice balance {invoice_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/admin/app-logs')
def get_app_logs(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin']))):
    """Get all application logs with search and filters (Admin only)"""
    try:
        username = request.query_params.get('username')
        module = request.query_params.get('module')
        action = request.query_params.get('action')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        keyword = request.query_params.get('keyword')
        
        query = db.query(AppLog)
        
        if username:
            query = query.filter(AppLog.username == username)
        if module:
            query = query.filter(AppLog.module == module)
        if action:
            query = query.filter(AppLog.action == action)
            
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(AppLog.created_at >= start_date_obj)
            except ValueError:
                pass
                
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(AppLog.created_at < end_date_obj)
            except ValueError:
                pass
                
        if keyword:
            query = query.filter(AppLog.details.ilike(f'%{keyword}%'))
            
        # Paginate results
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 100))
        
        _q = query.order_by(AppLog.created_at.desc())
        _total = _q.count()
        _pages = max(1, (_total + per_page - 1) // per_page)
        _items = _q.offset((page - 1) * per_page).limit(per_page).all()
        class _Pg: pass
        pagination = _Pg()
        pagination.items = _items
        pagination.page = page
        pagination.per_page = per_page
        pagination.total = _total
        pagination.pages = _pages
        pagination.has_next = page < _pages
        pagination.has_prev = page > 1
        
        return _json({
            'logs': [log.to_dict() for log in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': pagination.page
        }, 200)
    except Exception as e:
        logger.error(f"Error fetching app logs: {e}")
        return _json({'error': 'Failed to fetch logs'}, 500)
