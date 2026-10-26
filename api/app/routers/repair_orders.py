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
from app.foundation.idempotent import idempotent_create
from app.foundation.overrides import require_audit_reason
from app.foundation.versioning import bump_version, check_version, extract_version
from app.parts_flow import issue_on_ro_open
from app.pipeline import assert_can_open_ro_from_quote

logger = logging.getLogger(__name__)
router = APIRouter()


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


def _get_or_404(db: Session, model, pk):
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from datetime import datetime
import json


@router.get('/repair-orders')
def get_repair_orders(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    try:
        status = request.query_params.get('status')
        keyword = request.query_params.get('keyword')
        search_id = request.query_params.get('id')
        
        query = db.query(RepairOrder)
        
        if status and status != 'all':
            query = query.filter(RepairOrder.current_status == status)
        
        # Search by ID
        if search_id:
            try:
                repair_order_id = int(search_id)
                query = query.filter(RepairOrder.id == repair_order_id)
            except ValueError:
                # If ID is not a valid integer, return empty result
                return _json({'repair_orders': []})
        
        # Search by keyword
        if keyword:
            keyword_filter = f"%{keyword}%"
            query = query.filter(
                or_(
                    RepairOrder.customer_name.ilike(keyword_filter),
                    RepairOrder.customer_phone.ilike(keyword_filter),
                    RepairOrder.customer_address.ilike(keyword_filter),
                    RepairOrder.customer_reg_no.ilike(keyword_filter),
                    RepairOrder.customer_made.ilike(keyword_filter),
                    RepairOrder.customer_vin.ilike(keyword_filter),
                    RepairOrder.customer_color.ilike(keyword_filter),
                    RepairOrder.customer_chasis.ilike(keyword_filter),
                    RepairOrder.problem_description.ilike(keyword_filter),
                    RepairOrder.worker_name.ilike(keyword_filter)
                )
            )
        
        # Use joinedload to fetch related data in one query (fixes N+1 problem)
        repair_orders = query.options(
            joinedload(RepairOrder.parts),
            joinedload(RepairOrder.labour)
        ).order_by(desc(RepairOrder.created_at)).all()
        
        result = []
        for ro in repair_orders:
            # Parts and labour are now already loaded via joinedload
            parts = ro.parts
            labour = ro.labour
            
            repair_order_data = {
                'id': ro.id,
                'customer_name': ro.customer_name,
                'customer_phone': ro.customer_phone,
                'customer_address': ro.customer_address,
                'customer_reg_no': ro.customer_reg_no,
                'customer_made': ro.customer_made,
                'customer_mileage': ro.customer_mileage,
                'customer_vin': ro.customer_vin,
                'customer_color': ro.customer_color,
                'customer_chasis': ro.customer_chasis,
                'customer_id': ro.customer_id,
                'customer_code': f"CN{ro.customer_id:03d}" if ro.customer_id else "",
                'car_id': ro.car_id,
                'problem_description': ro.problem_description,
                'diagnosis_plan': ro.diagnosis_plan,
                'worker_id': ro.worker_id,
                'worker_name': ro.worker_name,
                'current_status': ro.current_status,
                'status_timeline': json.loads(ro.status_timeline) if ro.status_timeline else {},
                'vehicle_condition': json.loads(ro.vehicle_condition) if ro.vehicle_condition else {},
                'notes': ro.notes,
                'created_at': ro.created_at.isoformat() if ro.created_at else None,
                'updated_at': ro.updated_at.isoformat() if ro.updated_at else None,
                'created_by_user': ro.created_by_user,
                'updated_by_user': ro.updated_by_user,
                'workers_json': json.loads(ro.workers_json) if ro.workers_json else [],
                'parts': [
                    {
                        'id': part.id,
                        'inventory_id': part.inventory_id,
                        'description': part.description,
                        'part_number': part.part_number,
                        'quantity': part.quantity,
                        'status': part.status,
                        'ownership_type': getattr(part, 'ownership_type', 'shop_stock'),
                        'old_parts_returned': bool(getattr(part, 'old_parts_returned', False)),
                    } for part in parts
                ],
                'labour': [
                    {
                        'id': labour_item.id,
                        'description': labour_item.description,
                        'status': labour_item.status
                    } for labour_item in labour
                ]
            }
            result.append(repair_order_data)
        
        payload = {'repair_orders': result}

        # Keyword found nothing: suggest a spelling and the nearest customers.
        if keyword and not result:
            corpus = [row[0] for row in
                      db.query(RepairOrder.customer_name).distinct().all()]
            payload.update(suggestions_for(keyword, corpus))

        return _json(payload)
    
    except Exception as e:
        return _json({'error': str(e)}, 500)

@router.post('/repair-orders/from-quote/{quote_id:int}')
@idempotent_create
def create_ro_from_quote(
    quote_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager', 'manager', 'service_advisor'])),
):
    """Open RO from approved quote: issue reserved parts."""
    quote = db.get(Invoice, quote_id)
    if not quote:
        return _json({'error': 'Quote not found'}, 404)
    assert_can_open_ro_from_quote(db, quote)
    data = body or {}
    ro = RepairOrder(
        customer_name=quote.customer_name,
        customer_phone=quote.customer_phone or '',
        customer_address=quote.customer_address or '',
        customer_reg_no=quote.customer_reg_no or '',
        customer_made=quote.customer_made or '',
        customer_mileage=quote.customer_mileage or '',
        customer_vin=quote.customer_vin,
        customer_color=quote.customer_color,
        customer_chasis=quote.customer_chasis,
        problem_description=data.get('problem_description', ''),
        current_status='in_progress',
        created_by_user=current_user.username if current_user else None,
        customer_id=quote.customer_id,
        car_id=quote.car_id,
        visit_id=quote.visit_id,
        job_card_id=quote.job_card_id,
        quote_invoice_id=quote.id,
    )
    db.add(ro)
    db.flush()
    quote.repair_order_id = ro.id
    issue_on_ro_open(db, ro, quote, created_by=getattr(current_user, 'id', None))
    lab_statuses = [(l.approval_status or 'pending').lower() for l in (quote.labours or [])]
    lab_legacy = bool(lab_statuses) and all(s == 'pending' for s in lab_statuses)
    for lab in quote.labours or []:
        st = (lab.approval_status or 'pending').lower()
        if st == 'rejected':
            continue
        if st != 'approved' and not lab_legacy:
            continue
        db.add(
            RepairOrderLabour(
                repair_order_id=ro.id,
                description=lab.description,
                status='Approved',
                labour_code_id=lab.labour_code_id,
            )
        )
    if quote.visit_id:
        visit = db.get(Visit, quote.visit_id)
        if visit and not visit.repair_order_id:
            visit.repair_order_id = ro.id
    log_action(db, current_user, 'CREATE', 'repair_orders', ro.id, f"RO from quote #{quote.id}")
    db.commit()
    return _json({'id': ro.id, 'message': 'Repair order opened from quote'}, 201)


# Get a specific repair order by ID
@router.post('/repair-orders')
@idempotent_create
def create_repair_order(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    try:
        data = body or {}
        
        # Validate required fields
        if not data.get('customer_name'):
            return _json({'error': 'Customer name is required'}, 400)

        visit_id_raw = data.get('visit_id')
        visit_id = int(visit_id_raw) if visit_id_raw not in (None, '') else None
        quote_id = data.get('quote_invoice_id')
        quote = db.get(Invoice, int(quote_id)) if quote_id else None
        if quote:
            assert_can_open_ro_from_quote(db, quote)
        
        # Create repair order
        worker_ids = data.get('worker_ids', [])
        workers_list = []
        worker_id_val = None
        worker_name_val = ""
        
        if worker_ids:
            workers_db = db.query(Worker).filter(Worker.id.in_(worker_ids)).all()
            workers_db_dict = {w.id: w for w in workers_db}
            for wid in worker_ids:
                try:
                    wid_int = int(wid)
                    if wid_int in workers_db_dict:
                        w = workers_db_dict[wid_int]
                        workers_list.append({'id': w.id, 'name': f"{w.first_name} {w.last_name}"})
                except (ValueError, TypeError):
                    pass
            
            if workers_list:
                worker_id_val = workers_list[0]['id']
                worker_name_val = ", ".join([w['name'] for w in workers_list])
        else:
            # Fallback for single worker compatibility
            legacy_worker_id = data.get('worker_id')
            if legacy_worker_id and str(legacy_worker_id).strip():
                try:
                    legacy_worker_id = int(legacy_worker_id)
                    w = db.get(Worker, legacy_worker_id)
                    if w:
                        worker_id_val = w.id
                        worker_name_val = f"{w.first_name} {w.last_name}"
                        workers_list.append({'id': w.id, 'name': worker_name_val})
                except (ValueError, TypeError):
                    pass
            elif data.get('worker_name'):
                worker_name_val = data.get('worker_name')

        repair_order = RepairOrder(
            customer_name=data['customer_name'],
            customer_phone=data.get('customer_phone', ''),
            customer_address=data.get('customer_address', ''),
            customer_reg_no=data.get('customer_reg_no', ''),
            customer_made=data.get('customer_made', ''),
            customer_mileage=data.get('customer_mileage', ''),
            customer_vin=data.get('customer_vin', ''),
            customer_color=data.get('customer_color', ''),
            customer_chasis=data.get('customer_chasis', ''),
            problem_description=data.get('problem_description', ''),
            worker_id=worker_id_val,
            worker_name=worker_name_val,
            current_status='received',
            created_by_user=current_user.username if current_user else None,
            workers_json=json.dumps(workers_list) if workers_list else None,
            visit_id=visit_id,
            job_card_id=data.get('job_card_id'),
            quote_invoice_id=int(quote_id) if quote_id else None,
        )
        
        # Link to the customer and car this order was written for, and claim
        # the car for that customer if it had no owner yet.
        apply_links(db, repair_order, data)

        # Job card gate after linking: any resolved car needs completed check-in
        from app.visits import require_visit_for_job_card

        linked_visit = require_visit_for_job_card(
            db, car_id=repair_order.car_id, visit_id=visit_id
        )

        db.add(repair_order)
        db.flush()  # Get the ID

        if linked_visit is not None:
            linked_visit.repair_order_id = repair_order.id
            repair_order.visit_id = linked_visit.id
            if linked_visit.odometer and not repair_order.customer_mileage:
                repair_order.customer_mileage = linked_visit.odometer
            if linked_visit.reported_complaints and not repair_order.problem_description:
                repair_order.problem_description = linked_visit.reported_complaints

        if quote:
            quote.repair_order_id = repair_order.id
            issue_on_ro_open(db, repair_order, quote, created_by=getattr(current_user, 'id', None))
        
        # Process parts (legacy path when not from quote reserves)
        if data.get('parts') and not quote:
            success, processed_parts, inventory_errors = process_repair_order_parts(db, data['parts'], repair_order.id)
            
            if not success:
                db.rollback()
                return _json({'error': 'Failed to process parts', 'details': inventory_errors}, 400)
            
            for part_data in processed_parts:
                part = RepairOrderPart(
                    repair_order_id=repair_order.id,
                    description=part_data['description'],
                    quantity=part_data['quantity'],
                    inventory_id=part_data.get('inventory_id'),
                    part_number=part_data.get('part_number', ''),
                    status=part_data.get('status', 'pending'),
                    ownership_type=part_data.get('ownership_type', 'shop_stock'),
                    old_parts_returned=bool(part_data.get('old_parts_returned', False)),
                )
                db.add(part)
        
        # Process labour
        if data.get('labour'):
            for labour_data in data['labour']:
                labour = RepairOrderLabour(
                    repair_order_id=repair_order.id,
                    description=labour_data['description'],
                    status=labour_data.get('status', 'pending')
                )
                db.add(labour)
        
        log_action(db, current_user, 'CREATE', 'repair_orders', repair_order.id, f"Created repair order for customer {repair_order.customer_name} (Car: {repair_order.customer_made})")
        db.commit()
        
        return _json({
            'message': 'Repair order created successfully',
            'repair_order_id': repair_order.id,
            'visit_id': linked_visit.id if linked_visit else None,
        }, 201)
        
    except HTTPException as exc:
        db.rollback()
        detail = exc.detail
        if isinstance(detail, dict):
            return _json(detail, exc.status_code)
        return _json({'error': detail}, exc.status_code)
    except Exception as e:
        db.rollback()
        return _json({'error': str(e)}, 500)

# Update repair order status
@router.get('/repair-orders/assignable-workers')
def get_assignable_workers(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Just enough about each worker to put them on a job.

    Assigning a mechanic is part of writing a repair order, not part of HR, so
    it must not require the hr permission - an inventory manager needs to name
    who did the work without being able to see salaries, CNICs, addresses or
    phone numbers.

    Living under /api/repair-orders is what gives it the repair-order
    permission: PATH_PERMISSIONS matches on prefix, so /api/workers would have
    demanded hr no matter which roles the decorator allowed.

    Name, position and id only. Nothing here is worth withholding, and nothing
    withheld is needed.
    """
    try:
        workers = db.query(Worker).filter(Worker.status == 'active').order_by(
            Worker.first_name, Worker.last_name).all()
        return _json({
            'workers': [{
                'id': w.id,
                'first_name': w.first_name,
                'last_name': w.last_name,
                'position': w.position,
            } for w in workers]
        }, 200)
    except Exception as e:
        return _json({'error': str(e)}, 500)


# Get all repair orders with optional status filter
@router.get('/repair-orders/{repair_order_id:int}')
def get_repair_order(repair_order_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    try:
        # Use joinedload to fetch related data in one query
        repair_order = db.query(RepairOrder).options(
            joinedload(RepairOrder.parts),
            joinedload(RepairOrder.labour)
        ).get(repair_order_id)
        
        if not repair_order:
            return _json({'error': 'Repair order not found'}, 404)
        
        # Parts and labour are now already loaded via joinedload
        parts = repair_order.parts
        labour = repair_order.labour
        
        repair_order_data = {
            'id': repair_order.id,
            'customer_name': repair_order.customer_name,
            'customer_phone': repair_order.customer_phone,
            'customer_address': repair_order.customer_address,
            'customer_reg_no': repair_order.customer_reg_no,
            'customer_made': repair_order.customer_made,
            'customer_mileage': repair_order.customer_mileage,
            'customer_vin': repair_order.customer_vin,
            'customer_color': repair_order.customer_color,
            'customer_chasis': repair_order.customer_chasis,
            'customer_id': repair_order.customer_id,
            'customer_code': f"CN{repair_order.customer_id:03d}" if repair_order.customer_id else "",
            'car_id': repair_order.car_id,
            'problem_description': repair_order.problem_description,
            'diagnosis_plan': repair_order.diagnosis_plan,
            'worker_id': repair_order.worker_id,
            'worker_name': repair_order.worker_name,
            'current_status': repair_order.current_status,
            'status_timeline': json.loads(repair_order.status_timeline) if repair_order.status_timeline else {},
            'vehicle_condition': json.loads(repair_order.vehicle_condition) if repair_order.vehicle_condition else {},
            'notes': repair_order.notes,
            'created_at': repair_order.created_at.isoformat() if repair_order.created_at else None,
            'updated_at': repair_order.updated_at.isoformat() if repair_order.updated_at else None,
            'created_by_user': repair_order.created_by_user,
            'updated_by_user': repair_order.updated_by_user,
            'workers_json': json.loads(repair_order.workers_json) if repair_order.workers_json else [],
            'parts': [
                {
                    'id': part.id,
                    'inventory_id': part.inventory_id,
                    'description': part.description,
                    'part_number': part.part_number,
                    'quantity': part.quantity,
                    'status': part.status,
                    'ownership_type': getattr(part, 'ownership_type', 'shop_stock'),
                    'old_parts_returned': bool(getattr(part, 'old_parts_returned', False)),
                } for part in parts
            ],
            'labour': [
                {
                    'id': labour_item.id,
                    'description': labour_item.description,
                    'status': labour_item.status
                } for labour_item in labour
            ]
        }
        
        return _json(repair_order_data)
    
    except Exception as e:
        return _json({'error': str(e)}, 500)

# Create a new repair order
@router.put('/repair-orders/{repair_order_id:int}')
def update_repair_order(repair_order_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    try:
        repair_order = db.get(RepairOrder, repair_order_id)
        
        if not repair_order:
            return _json({'error': 'Repair order not found'}, 404)
        data = body or {}
        check_version(repair_order, extract_version(data))
            
        # Check if completed and user is not admin
        if repair_order.current_status == 'complete' and current_user.role != 'admin':
            return _json({'error': 'Completed repair orders can only be edited by administrators'}, 403)
        
        # Update basic information (only if provided and not None)
        if 'customer_name' in data and data['customer_name'] is not None:
            repair_order.customer_name = data['customer_name']
        if 'customer_phone' in data and data['customer_phone'] is not None:
            repair_order.customer_phone = data['customer_phone']
        if 'customer_address' in data and data['customer_address'] is not None:
            repair_order.customer_address = data['customer_address']
        if 'customer_reg_no' in data and data['customer_reg_no'] is not None:
            repair_order.customer_reg_no = data['customer_reg_no']
        if 'customer_made' in data and data['customer_made'] is not None:
            repair_order.customer_made = data['customer_made']
        if 'customer_mileage' in data and data['customer_mileage'] is not None:
            repair_order.customer_mileage = data['customer_mileage']
        if 'customer_vin' in data and data['customer_vin'] is not None:
            repair_order.customer_vin = data['customer_vin']
        if 'customer_color' in data and data['customer_color'] is not None:
            repair_order.customer_color = data['customer_color']
        if 'customer_chasis' in data and data['customer_chasis'] is not None:
            repair_order.customer_chasis = data['customer_chasis']
        # Re-link on every save: an edit can move the order to another
        # customer or car, and a car added mid-edit needs claiming.
        apply_links(db, repair_order, data)

        if 'problem_description' in data:
            repair_order.problem_description = data['problem_description']
            
        # Support multiple workers update
        if 'worker_ids' in data:
            worker_ids = data.get('worker_ids', [])
            workers_list = []
            worker_id_val = None
            worker_name_val = ""
            
            if worker_ids:
                workers_db = db.query(Worker).filter(Worker.id.in_(worker_ids)).all()
                workers_db_dict = {w.id: w for w in workers_db}
                for wid in worker_ids:
                    try:
                        wid_int = int(wid)
                        if wid_int in workers_db_dict:
                            w = workers_db_dict[wid_int]
                            workers_list.append({'id': w.id, 'name': f"{w.first_name} {w.last_name}"})
                    except (ValueError, TypeError):
                        pass
                
                if workers_list:
                    worker_id_val = workers_list[0]['id']
                    worker_name_val = ", ".join([w['name'] for w in workers_list])
            
            repair_order.worker_id = worker_id_val
            repair_order.worker_name = worker_name_val
            repair_order.workers_json = json.dumps(workers_list) if workers_list else None
        else:
            if 'worker_id' in data:
                repair_order.worker_id = int(data['worker_id']) if data['worker_id'] and str(data['worker_id']).strip() else None
                if repair_order.worker_id:
                    w = db.get(Worker, repair_order.worker_id)
                    if w:
                        repair_order.worker_name = f"{w.first_name} {w.last_name}"
                        repair_order.workers_json = json.dumps([{'id': w.id, 'name': repair_order.worker_name}])
                else:
                    repair_order.worker_name = ""
                    repair_order.workers_json = None
            elif 'worker_name' in data:
                repair_order.worker_name = data['worker_name']
                
        if 'diagnosis_plan' in data:
            repair_order.diagnosis_plan = data['diagnosis_plan']
        if 'vehicle_condition' in data:
            repair_order.vehicle_condition = json.dumps(data['vehicle_condition'])
        if 'notes' in data:
            repair_order.notes = data['notes']
        
        repair_order.updated_at = datetime.utcnow()
        repair_order.updated_by_user = current_user.username if current_user else None
        
        # Update parts if provided
        if 'parts' in data:
            # Get current parts for inventory comparison
            current_parts = db.query(RepairOrderPart).filter_by(repair_order_id=repair_order_id).all()
            current_parts_data = []
            for part in current_parts:
                current_parts_data.append({
                    'id': part.id,
                    'inventory_id': part.inventory_id,
                    'description': part.description,
                    'part_number': part.part_number,
                    'quantity': part.quantity,
                    'status': part.status,
                    'ownership_type': getattr(part, 'ownership_type', 'shop_stock'),
                    'old_parts_returned': bool(getattr(part, 'old_parts_returned', False)),
                })
            
            # Handle inventory changes
            success, inventory_errors = handle_repair_order_edit_inventory(db, current_parts_data, data['parts'], repair_order_id)
            
            if not success:
                db.rollback()
                return _json({'error': 'Failed to process inventory changes', 'inventory_errors': inventory_errors}, 400)
            
            # Delete existing parts
            db.query(RepairOrderPart).filter_by(repair_order_id=repair_order_id).delete()
            
            # Add new parts
            for part_data in data['parts']:
                part = RepairOrderPart(
                    repair_order_id=repair_order_id,
                    inventory_id=part_data.get('inventory_id'),
                    description=part_data.get('description'),
                    part_number=part_data.get('part_number'),
                    quantity=part_data.get('quantity', 1),
                    status=part_data.get('status', 'pending'),
                    ownership_type=part_data.get('ownership_type', 'shop_stock'),
                    old_parts_returned=bool(part_data.get('old_parts_returned', False)),
                )
                db.add(part)
            
            # Add inventory warnings if any
            if inventory_errors:
                response_data = {'message': 'Repair order updated successfully with some inventory warnings', 'inventory_warnings': inventory_errors}
            else:
                response_data = {'message': 'Repair order updated successfully'}
        
        # Update labour if provided
        if 'labour' in data:
            # Delete existing labour
            db.query(RepairOrderLabour).filter_by(repair_order_id=repair_order_id).delete()
            
            # Add new labour
            for labour_data in data['labour']:
                labour = RepairOrderLabour(
                    repair_order_id=repair_order_id,
                    description=labour_data.get('description'),
                    status=labour_data.get('status', 'pending')
                )
                db.add(labour)
        
        bump_version(repair_order)
        log_action(db, current_user, 'UPDATE', 'repair_orders', repair_order.id, f"Updated repair order details for customer {repair_order.customer_name}")
        db.commit()
        
        # Return appropriate response based on inventory warnings
        if 'response_data' in locals():
            return _json(response_data)
        else:
            return _json({'message': 'Repair order updated successfully'})
    
    except Exception as e:
        db.rollback()
        return _json({'error': str(e)}, 500)

# Delete repair order
@router.delete('/repair-orders/{repair_order_id:int}/delete')
def delete_repair_order(repair_order_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    try:
        repair_order = db.get(RepairOrder, repair_order_id)
        
        if not repair_order:
            return _json({'error': 'Repair order not found'}, 404)
        require_audit_reason(kind="delete")
            
        # Check if completed and user is not admin
        if repair_order.current_status == 'complete' and current_user.role != 'admin':
            return _json({'error': 'Completed repair orders can only be deleted by administrators'}, 403)
        
        # Get parts before deletion to restore inventory
        parts_to_restore = db.query(RepairOrderPart).filter_by(repair_order_id=repair_order_id).all()
        
        # Restore inventory for all parts using the utility function (logs transactions)
        if parts_to_restore:
            success, errors = restore_inventory_for_deleted_repair_order(db, parts_to_restore, repair_order_id)
            if errors:
                # Log errors but continue with deletion
                for error in errors:
                    print(f"Warning during inventory restore: {error}")
        
        # Soft-delete RO (hooks); children remain linked
        log_action(db, current_user, 'DELETE', 'repair_orders', repair_order_id, f"Deleted repair order ID {repair_order_id} for customer {repair_order.customer_name}")
        db.delete(repair_order)
        db.commit()
        
        return _json({'message': 'Repair order deleted successfully'})
    
    except Exception as e:
        db.rollback()
        return _json({'error': str(e)}, 500)

# Update specific part status
@router.put('/repair-orders/{repair_order_id:int}/labour/{labour_id:int}/status')
def update_labour_status(repair_order_id, labour_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    try:
        labour = db.query(RepairOrderLabour).filter_by(
            repair_order_id=repair_order_id, 
            id=labour_id
        ).first()
        
        if not labour:
            return _json({'error': 'Labour item not found'}, 404)
        
        data = body
        new_status = data.get('status')
        
        if not new_status:
            return _json({'error': 'Status is required'}, 400)
        
        labour.status = new_status
        log_action(db, current_user, 'UPDATE_LABOUR_STATUS', 'repair_orders', repair_order_id, f"Labour '{labour.description}' status updated to {new_status}")
        db.commit()
        
        return _json({'message': 'Labour status updated successfully'})
    
    except Exception as e:
        db.rollback()
        return _json({'error': str(e)}, 500)

@router.get('/repair-orders/{repair_order_id:int}/log')
def get_repair_order_log(repair_order_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """One repair order's history - status changes, edits, who did what."""
    try:
        order = db.get(RepairOrder, repair_order_id)
        if not order:
            return _json({'error': 'Repair order not found'}, 404)

        return _json({
            'kind': 'repair-order',
            'document_id': order.id,
            'reference': f"#{order.id}",
            'customer_name': order.customer_name,
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S') if order.created_at else '',
            'created_by': order.created_by_user,
            'current_status': order.current_status,
            'payments': [],
            'entries': document_log_entries(db, 'repair-order', order.id),
        }, 200)
    except Exception as e:
        return _json({'error': str(e)}, 500)


@router.get('/repair-orders/{repair_order_id:int}/logs')
def get_repair_order_logs(repair_order_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Get history logs for a specific repair order"""
    try:
        logs = db.query(AppLog).filter_by(module='repair_orders', reference_id=repair_order_id).order_by(AppLog.created_at.desc()).all()
        return _json([log.to_dict() for log in logs], 200)
    except Exception as e:
        return _json({'error': str(e)}, 500)


@router.put('/repair-orders/{repair_order_id:int}/parts/{part_id:int}/status')
def update_part_status(repair_order_id, part_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    try:
        part = db.query(RepairOrderPart).filter_by(
            repair_order_id=repair_order_id, 
            id=part_id
        ).first()
        
        if not part:
            return _json({'error': 'Part not found'}, 404)
        
        data = body
        new_status = data.get('status')
        
        if not new_status:
            return _json({'error': 'Status is required'}, 400)
        
        part.status = new_status
        log_action(db, current_user, 'UPDATE_PART_STATUS', 'repair_orders', repair_order_id, f"Part '{part.description}' status updated to {new_status}")
        db.commit()
        
        return _json({'message': 'Part status updated successfully'})
    
    except Exception as e:
        db.rollback()
        return _json({'error': str(e)}, 500)

# Update specific labour status
@router.put('/repair-orders/{repair_order_id:int}/status')
def update_repair_order_status(repair_order_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    try:
        repair_order = db.get(RepairOrder, repair_order_id)
        
        if not repair_order:
            return _json({'error': 'Repair order not found'}, 404)
            
        # Check if completed and user is not admin
        if repair_order.current_status == 'complete' and current_user.role != 'admin':
            return _json({'error': 'Completed repair orders can only be modified by administrators'}, 403)
        
        data = body
        new_status = data.get('status')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        
        if not new_status:
            return _json({'error': 'Status is required'}, 400)
        
        # Update current status
        old_status = repair_order.current_status
        repair_order.current_status = new_status
        
        # Update status timeline
        timeline = json.loads(repair_order.status_timeline) if repair_order.status_timeline else {}
        
        # Parse timestamp safely
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = parsed_timestamp.strftime('%H:%M')
        except (ValueError, AttributeError):
            # Fallback to current time if timestamp parsing fails
            parsed_timestamp = datetime.now()
            time_str = parsed_timestamp.strftime('%H:%M')
            timestamp = parsed_timestamp.isoformat()
        
        timeline[new_status] = {
            'date': timestamp,
            'time': time_str
        }
        repair_order.status_timeline = json.dumps(timeline)
        
        repair_order.updated_at = datetime.utcnow()
        repair_order.updated_by_user = current_user.username if current_user else None
        
        log_action(db, current_user, 'UPDATE_STATUS', 'repair_orders', repair_order.id, f"Status updated from {old_status} to {new_status}")
        db.commit()
        
        return _json({
            'message': 'Status updated successfully',
            'current_status': new_status,
            'status_timeline': timeline
        })
    
    except Exception as e:
        db.rollback()
        return _json({'error': str(e)}, 500)

# Update repair order
