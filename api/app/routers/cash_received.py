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
from sqlalchemy import desc, or_, and_, func, text, extract
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

logger = logging.getLogger(__name__)
router = APIRouter()


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


def _get_or_404(db: Session, model, pk):
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

from datetime import datetime, timedelta
from sqlalchemy import desc
from functools import wraps



def resolve_invoice(data):
    """Validate an optional invoice link. Returns (invoice, error_response)."""
    raw = data.get('invoice_id')
    if raw in (None, '', 'null'):
        return None, None
    try:
        invoice = db.get(Invoice, int(raw))
    except (TypeError, ValueError):
        return None, (_json({'error': 'invoice_id must be a number'}), 400)
    if not invoice:
        return None, (_json({'error': 'That invoice does not exist'}), 404)
    if (invoice.type_of or '').lower() != 'invoice':
        return None, (_json({
            'error': 'Payments can only be linked to an invoice, not a quote.'
        }), 400)
    return invoice, None


def apply_receipt_to_invoice(invoice, amount, method, user, receipt_id):
    """Record the receipt against the invoice so the money is entered once.

    Without this the link would be decorative: staff would still have to key the
    payment a second time through Update Balance, which is exactly the habit that
    left 313 invoices marked paid with no amount on them.
    """
    import json

    remaining = invoice_amount_remaining(invoice)
    if amount > remaining + 0.005:
        return _json({
            'error': (f'This receipt of {amount:.2f} PKR is more than the '
                      f'{remaining:.2f} PKR still owed on invoice #{invoice.id}.'),
            'remaining': remaining
        }, 400)

    invoice.paid_amount = round((invoice.paid_amount or 0.0) + amount, 2)
    invoice.balance = invoice_amount_remaining(invoice)
    invoice.status = calculate_invoice_status(invoice)

    try:
        history = json.loads(invoice.payments_history) if invoice.payments_history else []
    except (ValueError, TypeError):
        history = []
    history.append({
        'amount': amount,
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'person': user.username if user else 'system',
        'proof_path': None,
        'source': 'cash_received',
        'payment_method': method,
        'cash_received_id': receipt_id,
    })
    invoice.payments_history = json.dumps(history)
    return None


def assert_can_edit_cash_received(db: Session, current_user, cash_id: int) -> None:
    """Admins always; others cannot edit cash received older than 1 day."""
    if current_user.role == "admin":
        return
    cash_received = db.get(CashReceived, cash_id)
    if not cash_received:
        raise HTTPException(status_code=404, detail="Cash received record not found")
    if cash_received.created_at and cash_received.created_at < datetime.utcnow() - timedelta(days=1):
        raise HTTPException(status_code=403, detail="Cannot edit cash received records older than 1 day")


@router.get('/cash-received')
def get_cash_received(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get all cash received records with optional filtering"""
    try:
        # Get query parameters for filtering
        payment_method = request.query_params.get('payment_method')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        keyword = request.query_params.get('keyword')
        
        # Start with base query
        query = db.query(CashReceived)

        # Till view: money settling a customer invoice belongs to that invoice,
        # not to the drawer.
        if wants_till(request.query_params):
            query = till_receipts(query)

        # Apply filters
        if payment_method:
            query = query.filter(CashReceived.payment_method == payment_method)
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(CashReceived.date >= start_date_obj)
            except ValueError:
                return _json({'error': 'Invalid start_date format. Use YYYY-MM-DD'}, 400)
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(CashReceived.date <= end_date_obj)
            except ValueError:
                return _json({'error': 'Invalid end_date format. Use YYYY-MM-DD'}, 400)
        
        if keyword:
            query = query.filter(
                or_(
                    CashReceived.description.ilike(f'%{keyword}%'),
                    CashReceived.notes.ilike(f'%{keyword}%')
                )
            )
        
        # Order by date (newest first)
        cash_records = query.order_by(desc(CashReceived.date)).all()
        
        # Convert to JSON
        cash_data = []
        for cash in cash_records:
            cash_data.append({
                'id': cash.id,
                'date': cash.date.isoformat() if cash.date else None,
                'description': cash.description,
                'amount': cash.amount,
                'payment_method': cash.payment_method,
                'notes': cash.notes,
                'invoice_id': cash.invoice_id,
                'created_at': cash.created_at.isoformat() if cash.created_at else None,
                'updated_at': cash.updated_at.isoformat() if cash.updated_at else None
            })
        
        return _json(cash_data, 200)
        
    except Exception as e:
        return _json({'error': str(e)}, 500)

@router.post('/cash-received')
@guard_period(body_date('date'))
def create_cash_received(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None)):
    """Create a new cash received record"""
    try:
        data = body
        
        # Validate required fields
        required_fields = ['date', 'description', 'amount', 'payment_method']
        for field in required_fields:
            if field not in data or not data[field]:
                return _json({'error': f'{field} is required'}, 400)
        
        # Parse date
        try:
            cash_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return _json({'error': 'Invalid date format. Use YYYY-MM-DD'}, 400)
        
        # Validate amount
        try:
            amount = float(data['amount'])
            if amount < 0:
                return _json({'error': 'Amount must be positive'}, 400)
        except (ValueError, TypeError):
            return _json({'error': 'Invalid amount'}, 400)
        
        invoice, err = resolve_invoice(data)
        if err:
            return err

        # Create new cash received record
        new_cash = CashReceived(
            date=cash_date,
            description=data['description'],
            amount=amount,
            payment_method=data['payment_method'],
            notes=data.get('notes', ''),
            invoice_id=invoice.id if invoice else None
        )

        db.add(new_cash)
        # flush so the receipt has an id to reference from the invoice history
        # and from the audit log, which used to record None here.
        db.flush()

        if invoice:
            err = apply_receipt_to_invoice(
                invoice, amount, new_cash.payment_method, current_user, new_cash.id)
            if err:
                db.rollback()
                return err

        log_action(db, current_user, 'CREATE', 'cash_received', new_cash.id, f"Created cash received: {new_cash.description} ({new_cash.amount} PKR, Method: {new_cash.payment_method})")
        db.commit()
        
        # Return the created cash received record
        cash_data = {
            'id': new_cash.id,
            'date': new_cash.date.isoformat() if new_cash.date else None,
            'description': new_cash.description,
            'amount': new_cash.amount,
            'payment_method': new_cash.payment_method,
            'notes': new_cash.notes,
            'invoice_id': new_cash.invoice_id,
            'created_at': new_cash.created_at.isoformat() if new_cash.created_at else None,
            'updated_at': new_cash.updated_at.isoformat() if new_cash.updated_at else None
        }
        
        return _json(cash_data, 201)
        
    except Exception as e:
        db.rollback()
        return _json({'error': str(e)}, 500)

@router.get('/cash-received/summary')
def get_cash_received_summary(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get cash received summary statistics"""
    try:
        # Get query parameters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Start with base query
        query = db.query(CashReceived)

        # Same narrowing as the list, so the cards and the table agree.
        if wants_till(request.query_params):
            query = till_receipts(query)
        
        # Apply date filters if provided
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(CashReceived.date >= start_date_obj)
            except ValueError:
                return _json({'error': 'Invalid start_date format. Use YYYY-MM-DD'}, 400)
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(CashReceived.date <= end_date_obj)
            except ValueError:
                return _json({'error': 'Invalid end_date format. Use YYYY-MM-DD'}, 400)
        
        # Get all cash received records for the period
        cash_records = query.all()
        
        # Calculate summary
        total_amount = sum(cash.amount for cash in cash_records)
        
        # Group by payment method
        payment_method_totals = {}
        for cash in cash_records:
            method = cash.payment_method
            if method not in payment_method_totals:
                payment_method_totals[method] = 0
            payment_method_totals[method] += cash.amount
        
        # Get today's cash received
        today = datetime.now().date()
        today_cash = [cash for cash in cash_records if cash.date == today]
        today_total = sum(cash.amount for cash in today_cash)
        
        # Get this month's cash received
        current_month = datetime.now().replace(day=1).date()
        month_cash = [cash for cash in cash_records if cash.date >= current_month]
        month_total = sum(cash.amount for cash in month_cash)
        
        summary = {
            'total_amount': total_amount,
            'today_total': today_total,
            'month_total': month_total,
            'payment_method_totals': payment_method_totals,
            'total_records': len(cash_records),
            'today_records': len(today_cash),
            'month_records': len(month_cash)
        }
        
        return _json(summary, 200)
        
    except Exception as e:
        return _json({'error': str(e)}, 500)
@router.get('/cash-received/{cash_id:int}')
def get_cash_received_by_id(cash_id, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get a specific cash received record by ID"""
    try:
        cash_received = _get_or_404(db, CashReceived, cash_id)
        
        cash_data = {
            'id': cash_received.id,
            'date': cash_received.date.isoformat() if cash_received.date else None,
            'description': cash_received.description,
            'amount': cash_received.amount,
            'payment_method': cash_received.payment_method,
            'notes': cash_received.notes,
            'invoice_id': cash_received.invoice_id,
            'created_at': cash_received.created_at.isoformat() if cash_received.created_at else None,
            'updated_at': cash_received.updated_at.isoformat() if cash_received.updated_at else None
        }
        
        return _json(cash_data, 200)
        
    except Exception as e:
        return _json({'error': str(e)}, 500)

@router.put('/cash-received/{cash_id:int}')
@guard_both(CashReceived, 'cash_id')
def update_cash_received(cash_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(get_current_user)):
    """Update an existing cash received record"""
    try:
        assert_can_edit_cash_received(db, current_user, cash_id)
        cash_received = _get_or_404(db, CashReceived, cash_id)
        data = body
        
        # Validate required fields
        required_fields = ['date', 'description', 'amount', 'payment_method']
        for field in required_fields:
            if field not in data or not data[field]:
                return _json({'error': f'{field} is required'}, 400)
        
        # Parse date
        try:
            cash_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return _json({'error': 'Invalid date format. Use YYYY-MM-DD'}, 400)
        
        # Validate amount
        try:
            amount = float(data['amount'])
            if amount < 0:
                return _json({'error': 'Amount must be positive'}, 400)
        except (ValueError, TypeError):
            return _json({'error': 'Invalid amount'}, 400)
        
        # Update cash received record
        cash_received.date = cash_date
        cash_received.description = data['description']
        cash_received.amount = amount
        cash_received.payment_method = data['payment_method']
        cash_received.notes = data.get('notes', '')
        cash_received.updated_at = datetime.utcnow()

        log_action(db, current_user, 'UPDATE', 'cash_received', cash_received.id, f"Updated cash received record ID {cash_received.id}: {cash_received.description} ({cash_received.amount} PKR)")
        db.commit()
        
        # Return the updated cash received record
        cash_data = {
            'id': cash_received.id,
            'date': cash_received.date.isoformat() if cash_received.date else None,
            'description': cash_received.description,
            'amount': cash_received.amount,
            'payment_method': cash_received.payment_method,
            'notes': cash_received.notes,
            'invoice_id': cash_received.invoice_id,
            'created_at': cash_received.created_at.isoformat() if cash_received.created_at else None,
            'updated_at': cash_received.updated_at.isoformat() if cash_received.updated_at else None
        }
        
        return _json(cash_data, 200)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return _json({'error': str(e)}, 500)

@router.delete('/cash-received/{cash_id:int}')
@guard_period(record_date(CashReceived, 'cash_id'))
def delete_cash_received(cash_id, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Delete a cash received record"""
    try:
        assert_can_edit_cash_received(db, current_user, cash_id)
        cash_received = _get_or_404(db, CashReceived, cash_id)

        log_action(db, current_user, 'DELETE', 'cash_received', cash_id, f"Deleted cash received record ID {cash_id}: {cash_received.description} ({cash_received.amount} PKR)")
        db.delete(cash_received)
        db.commit()
        
        return _json({'message': 'Cash received record deleted successfully'}, 200)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return _json({'error': str(e)}, 500)

