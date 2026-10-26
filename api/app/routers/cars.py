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

from sqlalchemy.exc import SQLAlchemyError
import logging

# Configure logging
logger = logging.getLogger(__name__)


def validate_car_data(data):
    """Validate car data"""
    from app.foundation.validation import normalize_reg_no

    errors = []
    
    # All fields are now optional, but if provided, they must be valid
    # Make field
    if 'make' in data and data['make'] is not None and data['make'] != "N/A":
        if not str(data.get('make')).strip():
            errors.append("Car make must be a valid string if provided")
    
    # Model field
    if 'model' in data and data['model'] is not None and data['model'] != "N/A":
        if not str(data.get('model')).strip():
            errors.append("Car model must be a valid string if provided")
    
    # Plate number field
    if 'plate_no' in data and data['plate_no'] is not None and data['plate_no'] != "N/A":
        try:
            data['plate_no'] = normalize_reg_no(data['plate_no'])
        except ValueError as exc:
            errors.append(str(exc))
    
    # Mileage field
    if 'mileage' in data and data['mileage'] is not None and data['mileage'] != "N/A":
        if not str(data.get('mileage')).strip():
            errors.append("Mileage must be a valid string if provided")
    
    # Customer ID field (optional)
    if 'customer_id' in data and data['customer_id'] is not None and data['customer_id'] != '':
        try:
            int(data['customer_id'])
        except (ValueError, TypeError):
            errors.append("Customer ID must be a valid integer if provided")

    if 'year' in data and data['year'] not in (None, '', 'N/A'):
        try:
            year = int(data['year'])
            if year < 1950 or year > 2100:
                errors.append("Year must be between 1950 and 2100")
            else:
                data['year'] = year
        except (ValueError, TypeError):
            errors.append("Year must be a valid integer")
    
    # Optional: color and chasis_no can be empty, but if present, must be string
    if 'color' in data and data['color'] is not None and data['color'] != "N/A" and not isinstance(data['color'], str):
        errors.append("Color must be a string")
    if 'chasis_no' in data and data['chasis_no'] is not None and data['chasis_no'] != "N/A" and not isinstance(data['chasis_no'], str):
        errors.append("Chasis number must be a string")
    
    return errors

def validate_customer_data(data):
    """Validate customer data"""
    from app.customer_vehicle import CUSTOMER_TYPES
    from app.foundation.validation import normalize_pk_phone

    errors = []
    
    # All fields are now optional, but if provided, they must be valid
    # Name field
    if 'name' in data and data['name'] is not None and data['name'] != "N/A":
        if not str(data.get('name')).strip():
            errors.append("Customer name must be a valid string if provided")
    
    # Phone field — normalize to E.164 (+92…)
    if 'phone' in data and data['phone'] is not None and data['phone'] != "N/A":
        try:
            data['phone'] = normalize_pk_phone(data['phone'])
        except ValueError as exc:
            errors.append(str(exc))

    if 'alternate_phone' in data and data['alternate_phone'] not in (None, '', 'N/A'):
        try:
            data['alternate_phone'] = normalize_pk_phone(data['alternate_phone'])
        except ValueError as exc:
            errors.append(f"alternate_phone: {exc}")
    
    # Address field
    if 'address' in data and data['address'] is not None and data['address'] != "N/A":
        if not str(data.get('address')).strip():
            errors.append("Address must be a valid string if provided")

    if 'customer_type' in data and data['customer_type'] not in (None, ''):
        ctype = str(data['customer_type']).strip().lower()
        if ctype not in CUSTOMER_TYPES:
            errors.append(f"customer_type must be one of: {', '.join(CUSTOMER_TYPES)}")
        else:
            data['customer_type'] = ctype
    
    return errors


_WRITE_ROLES = [
    'admin', 'owner', 'manager', 'accountant', 'service_advisor',
    'inventory_manager', 'store_keeper',
]

# Customer routes
@router.get('/cars')
def get_cars(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """List cars with optional search + pagination. Returns array (legacy) or page envelope."""
    try:
        from app.customer_vehicle import car_dict

        q = (request.query_params.get('q') or '').strip()
        customer_id = request.query_params.get('customer_id')
        page = max(1, int(request.query_params.get('page') or 1))
        per_page = min(100, max(1, int(request.query_params.get('per_page') or 50)))
        paginate = 'page' in request.query_params or 'per_page' in request.query_params or bool(q)

        query = db.query(Car).outerjoin(Customer)
        if customer_id:
            query = query.filter(Car.customer_id == int(customer_id))
        if q:
            like = f'%{q}%'
            query = query.filter(
                or_(
                    Car.plate_no.ilike(like),
                    Car.vin.ilike(like),
                    Car.make.ilike(like),
                    Car.model.ilike(like),
                    Car.code.ilike(like),
                    Car.chasis_no.ilike(like),
                    Customer.name.ilike(like),
                    Customer.phone.ilike(like),
                )
            )
        query = query.order_by(Car.id.desc())
        total = query.count()
        rows = query.offset((page - 1) * per_page).limit(per_page).all() if paginate else query.limit(500).all()
        cars_data = [car_dict(car) for car in rows]
        if paginate:
            return _json({
                'cars': cars_data,
                'count': len(cars_data),
                'total': total,
                'page': page,
                'per_page': per_page,
            }, 200)
        return _json(cars_data, 200)
    except Exception as e:
        logger.error(f"Error fetching cars: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.post('/cars')
def create_car(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(_WRITE_ROLES))):
    """Create a vehicle, or reuse an existing one (same VIN / plate+owner) for intake."""
    try:
        from app.customer_vehicle import car_dict, find_existing_car

        data = body or {}
        if not data:
            return _json({'error': 'No data provided'}, 400)

        validation_errors = validate_car_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)

        customer_id = data.get('customer_id')
        customer = None
        if customer_id not in (None, '', 'N/A'):
            try:
                customer_id = int(customer_id)
                customer = db.get(Customer, customer_id)
                if not customer:
                    return _json({'error': 'Customer not found'}, 404)
            except (ValueError, TypeError):
                customer_id = None

        plate_no = data.get('plate_no')
        vin = str(data.get('vin', '')).strip().upper() if data.get('vin') else None
        if vin == '':
            vin = None

        # Reuse existing vehicle instead of duplicating (preserves history/ownership refs)
        reuse = find_existing_car(
            db, plate_no=plate_no, vin=vin, customer_id=customer_id
        )
        force_new = bool(data.get('force_new'))
        if reuse and not force_new:
            # Attach orphan / update light fields when same owner intakes again
            if customer_id and reuse.customer_id is None:
                reuse.customer_id = customer_id
            if data.get('mileage'):
                reuse.mileage = str(data.get('mileage')).strip()
            if data.get('notes') is not None:
                reuse.notes = str(data.get('notes') or '').strip() or None
            reuse.updated_by_user = current_user.username if current_user else None
            db.commit()
            db.refresh(reuse)
            return _json({
                'message': 'Existing vehicle reused',
                'reused': True,
                'car': car_dict(reuse),
            }, 200)

        if vin:
            existing_car = db.query(Car).filter_by(vin=vin).first()
            if existing_car and (not reuse or existing_car.id != reuse.id):
                return _json({
                    'error': 'Car with this VIN already exists',
                    'details': f'A car with VIN {vin} already exists.',
                    'existing_car_id': existing_car.id,
                    'car': car_dict(existing_car),
                }, 409)

        make = str(data.get('make') or '').strip() or None
        model = str(data.get('model') or '').strip() or None
        mileage = str(data.get('mileage') or '').strip() or None
        color = str(data.get('color') or '').strip() or None
        chasis_no = str(data.get('chasis_no') or '').strip() or None
        engine_no = str(data.get('engine_no') or '').strip() or None
        notes = str(data.get('notes') or '').strip() or None
        year = data.get('year')
        if year in ('', 'N/A'):
            year = None

        car = Car(
            make=make,
            model=model,
            year=year,
            plate_no=plate_no,
            mileage=mileage,
            vin=vin,
            color=color,
            chasis_no=chasis_no,
            engine_no=engine_no,
            notes=notes,
            customer_id=customer_id,
            created_by_user=current_user.username if current_user else None,
        )
        db.add(car)
        db.flush()
        if not car.code:
            from app.document_numbers import car_code

            car.code = car_code(car.id)
        db.commit()
        db.refresh(car)
        return _json({
            'message': 'Car created successfully',
            'reused': False,
            'car': car_dict(car),
        }, 201)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating car: {e}")
        return _json({'error': 'Database error occurred'}, 500)
    except Exception as e:
        logger.error(f"Unexpected error creating car: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/cars/customer/{customer_id:int}')
def get_cars_by_customer(customer_id, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get all cars for a specific customer"""
    try:
        if not customer_id or customer_id <= 0:
            return _json({'error': 'Invalid customer ID'}, 400)
        
        # Check if customer exists
        customer = db.get(Customer, customer_id)
        if not customer:
            return _json({'error': 'Customer not found'}, 404)
        
        cars = db.query(Car).filter_by(customer_id=customer_id).all()
        cars_data = []
        
        for car in cars:
            cars_data.append({
                'id': car.id,
                'make': car.make,
                'model': car.model,
                'plate_no': car.plate_no,
                'mileage': car.mileage,
                'customer_id': car.customer_id,
                'customer_name': customer.name,
                'customer_phone': customer.phone,
                'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return _json({
            'customer': {
                'id': customer.id,
                'code': customer.code,
                'name': customer.name,
                'phone': customer.phone,
                'address': customer.address
            },
            'cars': cars_data,
            'count': len(cars_data)
        }, 200)
        
    except Exception as e:
        logger.error(f"Error fetching cars for customer {customer_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.get('/cars/search')
def search_cars(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Search cars by plate, VIN, make/model, or customer name/phone."""
    try:
        from app.car_ownership import find_cars_for_history_search

        query = request.query_params.get('q', '').strip()
        
        if not query:
            return _json({'error': 'Search query is required'}, 400)
        
        search_results = find_cars_for_history_search(db, query)
        
        cars_data = []
        for car in search_results:
            cars_data.append({
                'id': car.id,
                'make': car.make,
                'model': car.model,
                'plate_no': car.plate_no,
                'mileage': car.mileage,
                'vin': car.vin,
                'customer_id': car.customer_id,
                'customer_name': car.customer.name if car.customer else None,
                'customer_code': car.customer.code if car.customer else None,
                'customer_phone': car.customer.phone if car.customer else None,
                'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S") if car.created_at else None,
                'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S") if car.updated_at else None,
            })
        
        payload = {
            'query': query,
            'results': cars_data,
            'count': len(cars_data)
        }

        if query and not cars_data:
            corpus = [row[0] for row in db.query(Car.plate_no).distinct().all() if row[0]]
            corpus += [row[0] for row in db.query(Car.vin).distinct().all() if row[0]]
            payload.update(suggestions_for(query, corpus))

        return _json(payload, 200)
        
    except Exception as e:
        logger.error(f"Error searching cars: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.get('/cars/{car_id:int}/history')
def get_car_history(
    car_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Unified timeline: visits/quotes, ROs, invoices, payments, parts, ownership."""
    from app.car_ownership import build_car_history

    kinds_raw = (request.query_params.get('kinds') or '').strip()
    kinds = {k.strip() for k in kinds_raw.split(',') if k.strip()} or None
    try:
        return _json(build_car_history(db, car_id, kinds=kinds), 200)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building car history {car_id}: {e}")
        return _json({'error': 'Failed to load car history'}, 500)


@router.get('/inspection-templates/default')
def get_default_inspection_template(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.visits import get_active_template

    tpl = get_active_template(db)
    return _json({"template": tpl.to_dict()}, 200)


@router.put('/inspection-templates/default')
def update_default_inspection_template(
    body: dict | None = Body(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'owner', 'manager'])),
):
    """Replace checklist points on the default template (configurable)."""
    from app.visits import ensure_default_inspection_template

    data = body or {}
    points = data.get("points")
    if not isinstance(points, list) or not points:
        return _json({"error": "points must be a non-empty list"}, 400)
    cleaned = []
    for idx, p in enumerate(points):
        if not isinstance(p, dict) or not p.get("key") or not p.get("label"):
            return _json({"error": f"Point {idx} needs key and label"}, 400)
        cleaned.append(
            {
                "key": str(p["key"]).strip(),
                "label": str(p["label"]).strip(),
                "category": str(p.get("category") or "general").strip(),
                "requires_photo": bool(p.get("requires_photo")),
                "sort_order": int(p.get("sort_order") or (idx + 1) * 10),
            }
        )
    tpl = ensure_default_inspection_template(db)
    tpl.points_json = json.dumps(cleaned)
    if data.get("name"):
        tpl.name = str(data["name"]).strip()
    tpl.updated_at = datetime.utcnow()
    db.commit()
    return _json({"message": "Template updated", "template": tpl.to_dict()}, 200)


@router.get('/cars/{car_id:int}/visits')
def list_car_visits(
    car_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    car = db.get(Car, car_id)
    if not car or getattr(car, "deleted_at", None) is not None:
        return _json({"error": "Car not found"}, 404)
    rows = (
        db.query(Visit)
        .options(joinedload(Visit.items), joinedload(Visit.signature), joinedload(Visit.customer))
        .filter(Visit.car_id == car_id)
        .order_by(Visit.check_in_at.desc(), Visit.id.desc())
        .all()
    )
    return _json({"visits": [v.to_dict() for v in rows], "count": len(rows)}, 200)


@router.post('/cars/{car_id:int}/visits')
def create_car_visit(
    car_id: int,
    body: dict | None = Body(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant', 'manager', 'service_advisor'])),
):
    """Digital check-in: odometer, fuel, complaints, multi-point inspection, signature required."""
    from app.visits import create_visit

    car = db.get(Car, car_id)
    if not car or getattr(car, "deleted_at", None) is not None:
        return _json({"error": "Car not found"}, 404)
    try:
        visit = create_visit(db, car=car, data=body or {}, user=current_user)
        db.commit()
        db.refresh(visit)
        return _json(
            {
                "message": "Check-in completed",
                "visit": visit.to_dict(),
            },
            201,
        )
    except HTTPException as exc:
        db.rollback()
        detail = exc.detail
        if isinstance(detail, dict):
            return _json(detail, exc.status_code)
        return _json({"error": detail}, exc.status_code)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating visit for car {car_id}: {e}")
        return _json({"error": "Failed to create check-in"}, 500)


@router.get('/visits/{visit_id:int}')
def get_visit_detail(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.visits import get_visit

    try:
        visit = get_visit(db, visit_id)
        car = visit.car
        return _json(
            {
                "visit": visit.to_dict(),
                "car": {
                    "id": car.id if car else None,
                    "make": car.make if car else None,
                    "model": car.model if car else None,
                    "plate_no": car.plate_no if car else None,
                    "vin": car.vin if car else None,
                },
            },
            200,
        )
    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            return _json(detail, exc.status_code)
        return _json({"error": detail}, exc.status_code)


@router.patch('/visits/{visit_id:int}')
def patch_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(['admin', 'accountant', 'service_advisor', 'manager', 'inventory_manager'])),
):
    """Update inspection notes, odometer, fuel, or checklist items/photos."""
    from app.visits import update_visit

    try:
        visit = update_visit(db, visit_id, body or {}, current_user)
        db.commit()
        return _json({"visit": visit.to_dict(), "message": "Visit updated"}, 200)
    except HTTPException as exc:
        db.rollback()
        detail = exc.detail
        if isinstance(detail, dict):
            return _json(detail, exc.status_code)
        return _json({"error": detail}, exc.status_code)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update visit {visit_id}: {e}")
        return _json({"error": "Failed to update visit"}, 500)


@router.get('/visits/{visit_id:int}/check-in-sheet')
def get_check_in_sheet(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Printable check-in sheet payload (frontend renders / prints)."""
    from app.visits import get_visit

    try:
        visit = get_visit(db, visit_id)
        car = visit.car
        return _json(
            {
                "title": "Vehicle check-in sheet",
                "printed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "visit": visit.to_dict(),
                "car": {
                    "id": car.id if car else None,
                    "make": car.make if car else None,
                    "model": car.model if car else None,
                    "plate_no": car.plate_no if car else None,
                    "vin": car.vin if car else None,
                    "color": car.color if car else None,
                },
                "customer": {
                    "id": visit.customer_id,
                    "name": visit.customer.name if visit.customer else None,
                    "phone": visit.customer.phone if visit.customer else None,
                },
            },
            200,
        )
    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            return _json(detail, exc.status_code)
        return _json({"error": detail}, exc.status_code)


@router.post('/cars/{car_id:int}/transfer')
async def transfer_car(
    car_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(['admin', 'accountant', 'manager', 'service_advisor'])),
):
    """Transfer car ownership. Evidence file is required. Invoices stay with original customer."""
    from app.car_ownership import transfer_car_ownership
    from app.foundation.context import set_reason

    try:
        form = await request.form()
        to_raw = form.get('to_customer_id')
        reason = (form.get('reason') or '').strip()
        date_raw = (form.get('transfer_date') or '').strip()
        evidence = form.get('evidence')
        if evidence is not None and not getattr(evidence, 'filename', None):
            evidence = None

        if not to_raw:
            return _json({'error': 'to_customer_id is required'}, 400)
        if not reason:
            return _json({'error': 'reason is required'}, 400)
        if not evidence:
            return _json({'error': 'evidence attachment is required'}, 400)

        try:
            to_customer_id = int(to_raw)
        except (TypeError, ValueError):
            return _json({'error': 'to_customer_id must be an integer'}, 400)

        if date_raw:
            try:
                transfer_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
            except ValueError:
                return _json({'error': 'transfer_date must be YYYY-MM-DD'}, 400)
        else:
            transfer_date = date.today()

        car = db.get(Car, car_id)
        if not car or getattr(car, 'deleted_at', None) is not None:
            return _json({'error': 'Car not found'}, 404)

        set_reason(reason)
        ownership = transfer_car_ownership(
            db,
            car=car,
            to_customer_id=to_customer_id,
            transfer_date=transfer_date,
            reason=reason,
            evidence_file=evidence,
            user=current_user,
        )
        db.commit()
        db.refresh(ownership)
        return _json(
            {
                'message': 'Car transferred successfully',
                'ownership': ownership.to_dict(),
                'car_id': car.id,
                'customer_id': car.customer_id,
            },
            201,
        )
    except HTTPException as exc:
        db.rollback()
        detail = exc.detail
        if isinstance(detail, dict):
            return _json(detail, exc.status_code)
        return _json({'error': detail}, exc.status_code)
    except Exception as e:
        db.rollback()
        logger.error(f"Error transferring car {car_id}: {e}")
        return _json({'error': 'Failed to transfer car'}, 500)

@router.get('/cars/{car_id:int}')
def get_car(car_id, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get specific car by ID"""
    try:
        from app.customer_vehicle import car_dict

        if not car_id or car_id <= 0:
            return _json({'error': 'Invalid car ID'}, 400)
        
        car = db.query(Car).outerjoin(Customer).filter(Car.id == car_id).first()
        if not car or getattr(car, 'deleted_at', None) is not None:
            return _json({'error': 'Car not found'}, 404)
        
        return _json(car_dict(car), 200)
        
    except Exception as e:
        logger.error(f"Error fetching car {car_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.put('/cars/{car_id:int}')
def update_car(car_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(_WRITE_ROLES))):
    """Update an existing car"""
    from app.foundation.versioning import bump_version, check_version, extract_version

    try:
        if not car_id or car_id <= 0:
            return _json({'error': 'Invalid car ID'}, 400)
        
        data = body
        
        if not data:
            return _json({'error': 'No data provided'}, 400)
        
        # Validate input data
        validation_errors = validate_car_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)
        
        # Find the car
        car = db.get(Car, car_id)
        if not car:
            return _json({'error': 'Car not found'}, 404)
        check_version(car, extract_version(data))
        
        # Check if customer exists (if customer_id is provided)
        customer_id = data.get('customer_id')
        customer = None
        if customer_id and customer_id != "N/A":
            try:
                customer_id = int(customer_id)
                customer = db.get(Customer, customer_id)
                if not customer:
                    return _json({'error': 'Customer not found'}, 404)
            except (ValueError, TypeError):
                customer_id = None
        
        # Get plate number (duplicate plate numbers are now allowed)
        plate_no = str(data.get('plate_no')).strip() if data.get('plate_no') else None
        
        from app.customer_vehicle import car_dict

        make = str(data.get('make') or '').strip() or None
        model = str(data.get('model') or '').strip() or None
        mileage = str(data.get('mileage') or '').strip() or None
        vin = str(data.get('vin') or '').strip().upper() or None
        color = str(data.get('color') or '').strip() or None
        chasis_no = str(data.get('chasis_no') or '').strip() or None
        engine_no = str(data.get('engine_no') or '').strip() or None
        notes = str(data.get('notes') or '').strip() or None
        year = data.get('year')
        if year in ('', 'N/A', None):
            year = None
        
        # Update car
        try:
            car.make = make
            car.model = model
            car.year = year
            car.plate_no = plate_no
            car.mileage = mileage
            car.vin = vin
            car.color = color
            car.chasis_no = chasis_no
            car.engine_no = engine_no
            car.notes = notes
            car.customer_id = customer_id
            car.updated_by_user = current_user.username if current_user else None
            bump_version(car)
            
            db.commit()
            db.refresh(car)
            return _json({
                'message': 'Car updated successfully',
                'car': car_dict(car),
            }, 200)
        
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating car {car_id}: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Unexpected error updating car {car_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.delete('/cars/{car_id:int}')
def delete_car(car_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Delete a car"""
    try:
        if not car_id or car_id <= 0:
            return _json({'error': 'Invalid car ID'}, 400)
        
        # Find the car
        car = db.get(Car, car_id)
        if not car:
            return _json({'error': 'Car not found'}, 404)
        
        # Delete car
        try:
            db.delete(car)
            db.commit()
            
            logger.info(f"Car deleted successfully: ID {car_id}")
            
            return _json({
                'message': 'Car deleted successfully',
                'deleted_car_id': car_id
            }, 200)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting car {car_id}: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Unexpected error deleting car {car_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/customers')
def get_customers(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """List customers with search + pagination. Array when unpaginated (legacy)."""
    try:
        from app.customer_vehicle import customer_dict

        q = (request.query_params.get('q') or '').strip()
        page = max(1, int(request.query_params.get('page') or 1))
        per_page = min(100, max(1, int(request.query_params.get('per_page') or 50)))
        paginate = 'page' in request.query_params or 'per_page' in request.query_params or bool(q)

        query = db.query(Customer)
        if q:
            like = f'%{q}%'
            query = query.filter(
                or_(
                    Customer.name.ilike(like),
                    Customer.phone.ilike(like),
                    Customer.alternate_phone.ilike(like),
                    Customer.address.ilike(like),
                    Customer.code.ilike(like),
                )
            )
        query = query.order_by(Customer.id.desc())
        total = query.count()
        rows = query.offset((page - 1) * per_page).limit(per_page).all() if paginate else query.limit(500).all()
        data = [customer_dict(c) for c in rows]
        if paginate:
            return _json({
                'customers': data,
                'count': len(data),
                'total': total,
                'page': page,
                'per_page': per_page,
            }, 200)
        return _json(data, 200)
    except Exception as e:
        logger.error(f"Error fetching customers: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.get('/customers/by-phone')
def customers_by_phone(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Search by phone before creating a customer (exact / alternate / suffix)."""
    from app.customer_vehicle import customer_dict, find_customers_by_phone

    phone = (request.query_params.get('phone') or '').strip()
    if not phone:
        return _json({'error': 'phone is required'}, 400)
    rows = find_customers_by_phone(db, phone, limit=20)
    return _json({
        'phone': phone,
        'results': [customer_dict(c, include_vehicles=True) for c in rows],
        'count': len(rows),
        'duplicate': len(rows) > 0,
        'message': f'{len(rows)} customer(s) match this phone' if rows else None,
    }, 200)


@router.get('/customers/{customer_id:int}')
def get_customer_detail(customer_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Customer profile: vehicles, ownership, previous ROs/estimates/invoices/balances."""
    from app.customer_vehicle import load_customer_bundle

    bundle = load_customer_bundle(db, customer_id)
    if not bundle:
        return _json({'error': 'Customer not found'}, 404)
    return _json(bundle, 200)


@router.post('/customers')
def create_customer(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(_WRITE_ROLES))):
    """Create a customer. Phone duplicates return 409 unless force=true."""
    try:
        from app.customer_vehicle import customer_dict, find_customers_by_phone

        data = body or {}
        if not data:
            return _json({'error': 'No data provided'}, 400)

        validation_errors = validate_customer_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)

        name = str(data.get('name') or '').strip() or None
        phone = data.get('phone')
        if phone is not None:
            phone = str(phone).strip() or None
        address = str(data.get('address') or '').strip() or None
        alternate_phone = data.get('alternate_phone')
        if alternate_phone not in (None, '', 'N/A'):
            alternate_phone = str(alternate_phone).strip()
        else:
            alternate_phone = None
        customer_type = (data.get('customer_type') or 'retail').strip().lower()
        notes = str(data.get('notes') or '').strip() or None
        force = bool(data.get('force'))

        phone_matches = find_customers_by_phone(db, phone, limit=5) if phone else []
        if phone_matches and not force:
            return _json({
                'error': 'Possible duplicate customer',
                'details': 'A customer with this phone already exists. Search by phone or pass force=true to create anyway.',
                'duplicate': True,
                'matches': [customer_dict(c, include_vehicles=True) for c in phone_matches],
                'existing_customer_id': phone_matches[0].id,
            }, 409)

        customer = Customer(
            name=name,
            phone=phone,
            alternate_phone=alternate_phone,
            address=address,
            customer_type=customer_type,
            notes=notes,
            consent_whatsapp=bool(data.get('consent_whatsapp', False)),
            consent_sms=bool(data.get('consent_sms', False)),
            consent_call=bool(data.get('consent_call', True)),
            created_by_user=current_user.username if current_user else None,
        )
        db.add(customer)
        db.flush()
        if not customer.code:
            from app.document_numbers import customer_code

            customer.code = customer_code(customer.id)
        db.commit()
        db.refresh(customer)
        return _json({
            'message': 'Customer created successfully',
            'customer': customer_dict(customer, include_vehicles=True),
        }, 201)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating customer: {e}")
        return _json({'error': 'Database error occurred'}, 500)
    except Exception as e:
        logger.error(f"Unexpected error creating customer: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.get('/customers/search')
def search_customers(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Search customers by name, phone, alternate phone, address, code."""
    try:
        from app.customer_vehicle import customer_dict

        query = request.query_params.get('q', '').strip()
        if not query:
            return _json({'error': 'Search query is required'}, 400)

        like = f'%{query}%'
        search_results = db.query(Customer).filter(
            or_(
                Customer.name.ilike(like),
                Customer.phone.ilike(like),
                Customer.alternate_phone.ilike(like),
                Customer.address.ilike(like),
                Customer.code.ilike(like),
            )
        ).order_by(Customer.name).limit(50).all()

        customers_data = [customer_dict(c) for c in search_results]
        payload = {
            'query': query,
            'results': customers_data,
            'count': len(customers_data),
        }
        if query and not customers_data:
            corpus = [row[0] for row in db.query(Customer.name).distinct().all() if row[0]]
            payload.update(suggestions_for(query, corpus))
        return _json(payload, 200)
    except Exception as e:
        logger.error(f"Error searching customers: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.put('/customers/{customer_id:int}')
def update_customer(customer_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(_WRITE_ROLES))):
    """Update an existing customer"""
    try:
        from app.customer_vehicle import customer_dict
        from app.foundation.versioning import check_version

        if not customer_id or customer_id <= 0:
            return _json({'error': 'Invalid customer ID'}, 400)

        data = body or {}
        if not data:
            return _json({'error': 'No data provided'}, 400)

        validation_errors = validate_customer_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)

        customer = db.get(Customer, customer_id)
        if not customer or getattr(customer, 'deleted_at', None) is not None:
            return _json({'error': 'Customer not found'}, 404)

        if 'version' in data:
            try:
                check_version(customer, data.get('version'))
            except HTTPException as exc:
                return _json(exc.detail if isinstance(exc.detail, dict) else {'error': exc.detail}, exc.status_code)

        if 'name' in data:
            customer.name = str(data.get('name') or '').strip() or None
        if 'phone' in data:
            customer.phone = data.get('phone')
        if 'alternate_phone' in data:
            alt = data.get('alternate_phone')
            customer.alternate_phone = str(alt).strip() if alt not in (None, '', 'N/A') else None
        if 'address' in data:
            customer.address = str(data.get('address') or '').strip() or None
        if 'customer_type' in data and data.get('customer_type'):
            customer.customer_type = str(data['customer_type']).strip().lower()
        if 'notes' in data:
            customer.notes = str(data.get('notes') or '').strip() or None
        if 'consent_whatsapp' in data:
            customer.consent_whatsapp = bool(data.get('consent_whatsapp'))
        if 'consent_sms' in data:
            customer.consent_sms = bool(data.get('consent_sms'))
        if 'consent_call' in data:
            customer.consent_call = bool(data.get('consent_call'))
        customer.updated_by_user = current_user.username if current_user else None
        if hasattr(customer, 'version') and customer.version is not None:
            customer.version = int(customer.version) + 1

        db.commit()
        db.refresh(customer)
        return _json({
            'message': 'Customer updated successfully',
            'customer': customer_dict(customer, include_vehicles=True),
        }, 200)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating customer {customer_id}: {e}")
        return _json({'error': 'Database error occurred'}, 500)
    except Exception as e:
        logger.error(f"Unexpected error updating customer {customer_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.delete('/customers/{customer_id:int}')
def delete_customer(customer_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'owner', 'manager']))):
    """Soft-delete a customer (foundation Session.delete hook)."""
    try:
        if not customer_id or customer_id <= 0:
            return _json({'error': 'Invalid customer ID'}, 400)
        customer = db.get(Customer, customer_id)
        if not customer or getattr(customer, 'deleted_at', None) is not None:
            return _json({'error': 'Customer not found'}, 404)
        # Detach vehicles so history/ownership refs stay on cars
        db.query(Car).filter(Car.customer_id == customer_id).update(
            {Car.customer_id: None}, synchronize_session=False
        )
        db.delete(customer)
        db.commit()
        return _json({
            'message': 'Customer deleted successfully',
            'deleted_customer_id': customer_id,
        }, 200)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deleting customer {customer_id}: {e}")
        return _json({'error': 'Database error occurred'}, 500)
    except Exception as e:
        logger.error(f"Unexpected error deleting customer {customer_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

# Car routes
