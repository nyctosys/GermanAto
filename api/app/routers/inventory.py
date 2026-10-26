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
from sqlalchemy import desc, or_, and_, func, text, extract, asc, case
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

logger = logging.getLogger(__name__)
router = APIRouter()


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


def _get_or_404(db: Session, model, pk):
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

import re
from sqlalchemy import func, false
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from datetime import datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo
import logging
import os
import uuid
from app.log_utils import secure_filename

# Business day boundary for opening/closing rollover (matches frontend Asia/Karachi usage)
BUSINESS_TZ = ZoneInfo('Asia/Karachi')

# Configure logging
logger = logging.getLogger(__name__)


# Configuration for file uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Save uploaded file and return the relative path (Flask FileStorage or UploadFile)."""
    filename = getattr(file, "filename", None) or ""
    if not file or not filename:
        return None

    if not allowed_file(filename):
        raise ValueError("Invalid file type. Only image files are allowed.")

    file_extension = filename.rsplit(".", 1)[1].lower()
    secure_name = secure_filename(f"{uuid.uuid4()}.{file_extension}")
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file_path = os.path.join(UPLOAD_FOLDER, secure_name)
    if hasattr(file, "save"):
        file.save(file_path)
    else:
        with open(file_path, "wb") as out:
            out.write(file.file.read())
    return f"uploads/{secure_name}"


async def _inventory_form_or_json(request: Request):
    """Parse multipart (optional image) or JSON body for inventory create/update."""
    ct = request.headers.get("content-type") or ""
    if "multipart/form-data" in ct:
        form = await request.form()
        data = {k: v for k, v in form.items() if not hasattr(v, "filename")}
        image = form.get("image")
        if image is not None and not getattr(image, "filename", None):
            image = None
        return data, image
    try:
        data = await request.json()
    except Exception:
        data = None
    return data, None

def validate_inventory_data(data):
    """Validate inventory data"""
    errors = []
    
    # Required fields
    if not data.get('name') or not str(data.get('name')).strip():
        errors.append("Item name is required")
    
    if not data.get('category') or not str(data.get('category')).strip():
        errors.append("Category is required")
    
    # Validate numeric fields
    try:
        quantity = int(data.get('quantity', 0))
        if quantity < 0:
            errors.append("Quantity cannot be negative")
    except (ValueError, TypeError):
        errors.append("Quantity must be a valid number")
    
    # Validate reorder fields
    try:
        reorder_level = int(data.get('reorder_level', 5))
        if reorder_level < 0:
            errors.append("Reorder level cannot be negative")
    except (ValueError, TypeError):
        errors.append("Reorder level must be a valid number")
    
    return errors

def clean_optional_text(value):
    if value is None:
        return None

    value = str(value).strip()
    return value or None

def get_business_now():
    """Current datetime in the shop business timezone."""
    return datetime.now(BUSINESS_TZ)


def get_business_day_bounds(business_day):
    """Return naive-UTC [start, end) bounds for a Asia/Karachi business day.

    InventoryTransaction.created_at is stored as naive UTC via datetime.utcnow().
    """
    start_local = datetime.combine(business_day, time.min, tzinfo=BUSINESS_TZ)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def classify_movement_quantity(quantity):
    """Split a signed movement into (inbound, outbound) absolute quantities."""
    quantity = quantity or 0
    if quantity > 0:
        return quantity, 0
    if quantity < 0:
        return 0, abs(quantity)
    return 0, 0


def to_business_date(created_at):
    """Convert a stored naive-UTC timestamp to the shop business calendar date."""
    if created_at is None:
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at.astimezone(BUSINESS_TZ).date()


def get_inventory_movement_totals(db: Session, items, business_day=None):
    """Return day-scoped opening/inbound/outbound/closing for inventory cards.

    Cards are always for one business day (default: today in Asia/Karachi).

        Opening (today) = Closing (yesterday)
        Opening + Purchases - Sales = Closing (today / current stock)

    Only today's movements count as purchases/sales. Opening is reconstructed as
    current stock minus today's net change, so a new calendar day automatically
    rolls yesterday's closing into today's opening with no batch job.
    """
    if business_day is None:
        business_day = get_business_now().date()

    day_start, day_end = get_business_day_bounds(business_day)
    item_ids = [item.id for item in items]
    movement_totals = {
        item.id: {
            'opening_quantity': item.quantity,
            'purchases_quantity': 0,
            'sales_quantity': 0,
            'adjustments_quantity': 0,
            'closing_quantity': item.quantity,
            'movement_date': business_day.isoformat(),
        }
        for item in items
    }

    if not item_ids:
        return movement_totals

    transactions = db.query(InventoryTransaction).filter(
        InventoryTransaction.inventory_id.in_(item_ids),
        InventoryTransaction.created_at >= day_start,
        InventoryTransaction.created_at < day_end,
    ).all()

    for transaction in transactions:
        item_totals = movement_totals[transaction.inventory_id]
        if transaction.transaction_type == 'adjustment':
            item_totals['adjustments_quantity'] += transaction.quantity
        else:
            inbound, outbound = classify_movement_quantity(transaction.quantity)
            item_totals['purchases_quantity'] += inbound
            item_totals['sales_quantity'] += outbound

    for item in items:
        item_totals = movement_totals[item.id]
        item_totals['opening_quantity'] = (
            item.quantity
            - item_totals['purchases_quantity']
            + item_totals['sales_quantity']
            - item_totals['adjustments_quantity']
        )

    return movement_totals


def build_item_daily_ledger(db: Session, item):
    """Build date-wise opening/in/out/closing rows for one inventory item.

    Walks every logged transaction chronologically so each day's closing becomes
    the next day's opening. Days with no movement are included consecutively
    from the earliest transaction through today.
    """
    business_today = get_business_now().date()
    transactions = (
        db.query(InventoryTransaction)
        .filter(InventoryTransaction.inventory_id == item.id)
        .order_by(InventoryTransaction.created_at.asc(), InventoryTransaction.id.asc())
        .all()
    )

    net_all = sum((transaction.quantity or 0) for transaction in transactions)
    running_quantity = item.quantity - net_all

    daily_rows = []
    transaction_rows = []
    grouped = {}

    for transaction in transactions:
        txn_date = to_business_date(transaction.created_at)
        if txn_date is None:
            continue
        grouped.setdefault(txn_date, []).append(transaction)

    if not grouped:
        return {
            'daily_rows': [{
                'date': business_today.isoformat(),
                'opening': item.quantity,
                'in_quantity': 0,
                'out_quantity': 0,
                'adjustments_quantity': 0,
                'closing': item.quantity,
            }],
            'transactions': [],
            'movement_date': business_today.isoformat(),
        }

    start_date = min(grouped.keys())
    end_date = business_today
    
    current_date = start_date
    while current_date <= end_date:
        opening = running_quantity
        inbound_total = 0
        outbound_total = 0
        adjustments_total = 0

        if current_date in grouped:
            day_transactions = grouped[current_date]
            for transaction in day_transactions:
                quantity = transaction.quantity or 0
                if transaction.transaction_type == 'adjustment':
                    adjustments_total += quantity
                else:
                    inbound, outbound = classify_movement_quantity(quantity)
                    inbound_total += inbound
                    outbound_total += outbound
                running_quantity += quantity

                created_local = transaction.created_at
                if created_local and created_local.tzinfo is None:
                    created_local = created_local.replace(tzinfo=timezone.utc).astimezone(BUSINESS_TZ)
                elif created_local:
                    created_local = created_local.astimezone(BUSINESS_TZ)

                transaction_rows.append({
                    'id': transaction.id,
                    'date': current_date.isoformat(),
                    'datetime': created_local.strftime('%Y-%m-%d %H:%M:%S') if created_local else '',
                    'transaction_type': transaction.transaction_type,
                    'in_quantity': 0 if transaction.transaction_type == 'adjustment' else (quantity if quantity > 0 else 0),
                    'out_quantity': 0 if transaction.transaction_type == 'adjustment' else (abs(quantity) if quantity < 0 else 0),
                    'quantity': quantity,
                    'previous_quantity': transaction.previous_quantity,
                    'new_quantity': transaction.new_quantity,
                    'reference_description': transaction.reference_description,
                    'notes': transaction.notes,
                    'repair_order_id': transaction.repair_order_id,
                })

        daily_rows.append({
            'date': current_date.isoformat(),
            'opening': opening,
            'in_quantity': inbound_total,
            'out_quantity': outbound_total,
            'adjustments_quantity': adjustments_total,
            'closing': running_quantity,
        })
        
        current_date += timedelta(days=1)

    return {
        'daily_rows': daily_rows,
        'transactions': transaction_rows,
        'movement_date': business_today.isoformat(),
    }


def code_matches(column, term):
    """Match a manufacturer/OEM code ignoring spaces, hyphens and case.

    Codes are written differently everywhere they appear - "11 427 583 220" in
    the system, "11427583220" on the box, "11-427-583-220" on an invoice. A
    plain LIKE finds none of the others, which makes searching by the code (the
    way a parts person actually works) fail.
    """
    stripped = re.sub(r"[^A-Za-z0-9]", "", term or "")
    if not stripped:
        return false()          # a no-op inside or_(), never None
    bare = func.replace(func.replace(func.replace(column, " ", ""), "-", ""), ".", "")
    return bare.ilike(f"%{stripped}%")


def inventory_item_to_dict(item, movement_totals=None):
    reserved = int(getattr(item, 'reserved', 0) or 0)
    on_hand = int(item.quantity or 0)
    item_data = {
        'id': item.id,
        'part_number': item.part_number,
        'barcode': item.barcode,
        'manufacturer_part_number': item.manufacturer_part_number,
        'name': item.name,
        'category': item.category,
        'quantity': on_hand,
        'on_hand': on_hand,
        'reserved': reserved,
        'available': on_hand - reserved,
        'price': float(item.price or 0),
        'avg_cost': float(getattr(item, 'avg_cost', 0) or 0),
        'description': item.description,
        'location': item.location,
        'reorder_level': item.reorder_level,
        'reorder_quantity': getattr(item, 'reorder_quantity', 10),
        'min_level': getattr(item, 'min_level', None),
        'max_level': getattr(item, 'max_level', None),
        'superseded_by_id': getattr(item, 'superseded_by_id', None),
        'alternate_codes': getattr(item, 'alternate_codes', None),
        'pending_purchase': bool(getattr(item, 'pending_purchase', False)),
        'image_path': item.image_path,
        'version': getattr(item, 'version', 1),
        'created_at': item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else None,
        'updated_at': item.updated_at.strftime("%Y-%m-%d %H:%M:%S") if item.updated_at else None,
    }

    if movement_totals and item.id in movement_totals:
        item_data.update(movement_totals[item.id])
    else:
        item_data['movement_date'] = get_business_now().date().isoformat()
        item_data['opening_quantity'] = item.quantity
        item_data['purchases_quantity'] = 0
        item_data['sales_quantity'] = 0
        item_data['adjustments_quantity'] = 0

    return item_data

def inventory_item_detail_to_dict(db: Session, item, business_day=None):
    return inventory_item_to_dict(
        item,
        get_inventory_movement_totals(db, [item], business_day=business_day)
    )

def find_inventory_item_by_code(db: Session, code):
    code = clean_optional_text(code)
    if not code:
        return None

    item = (
        db.query(Inventory).filter(Inventory.barcode == code).first()
        or db.query(Inventory).filter(Inventory.manufacturer_part_number == code).first()
        or db.query(Inventory).filter(Inventory.part_number == code).first()
    )
    if item:
        # Follow supersession chain to the active part when present.
        seen = set()
        while getattr(item, 'superseded_by_id', None) and item.id not in seen:
            seen.add(item.id)
            nxt = db.get(Inventory, item.superseded_by_id)
            if not nxt:
                break
            item = nxt
        return item

    # Cross-reference / alternate codes (comma-separated)
    for row in db.query(Inventory).filter(Inventory.alternate_codes.isnot(None)).all():
        codes = [c.strip() for c in (row.alternate_codes or '').replace(';', ',').split(',') if c.strip()]
        if code in codes or code.upper() in {c.upper() for c in codes}:
            return row
    return None

def ensure_unique_inventory_codes(db: Session, barcode=None, manufacturer_part_number=None, item_id: int=None):
    if barcode:
        existing = db.query(Inventory).filter(Inventory.barcode == barcode)
        if item_id:
            existing = existing.filter(Inventory.id != item_id)
        if existing.first():
            return f"Barcode {barcode} is already assigned to another inventory item"

    if manufacturer_part_number:
        existing = db.query(Inventory).filter(
            Inventory.manufacturer_part_number == manufacturer_part_number
        )
        if item_id:
            existing = existing.filter(Inventory.id != item_id)
        if existing.first():
            return f"Manufacturer part number {manufacturer_part_number} is already assigned to another inventory item"

    return None


def inventory_database_error_message(error):
    """Turn opaque SQLAlchemy failures into actionable API errors."""
    original = getattr(error, 'orig', None)
    detail = str(original or error)

    if isinstance(error, OperationalError) or 'Unknown column' in detail:
        missing = None
        if 'barcode' in detail:
            missing = 'barcode'
        elif 'manufacturer_part_number' in detail:
            missing = 'manufacturer_part_number'
        if missing:
            return (
                f"Database schema is missing the '{missing}' column. "
                "Run: python migrate_release_schema.py"
            )
        return (
            "Database schema is out of date for inventory. "
            "Run: python migrate_release_schema.py"
        )

    if isinstance(error, IntegrityError) or 'Duplicate entry' in detail:
        if 'barcode' in detail:
            return "That barcode is already assigned to another inventory item"
        if 'manufacturer_part_number' in detail:
            return "That manufacturer part number is already assigned to another inventory item"
        if 'part_number' in detail:
            return "Could not allocate a unique part number. Please try saving again."
        return "That inventory item conflicts with an existing unique value"

    return "Database error occurred"

@router.get('/inventory')
def get_inventory(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get inventory items with pagination"""
    try:
        # Get pagination parameters
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 50))
        
        # Limit per_page to prevent excessive memory usage
        per_page = min(per_page, 200)
        
        # Get search parameters
        search = request.query_params.get('search', '').strip()
        category = request.query_params.get('category', '').strip()
        
        # Build query
        query = db.query(Inventory)
        
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    Inventory.name.ilike(search_filter),
                    Inventory.part_number.ilike(search_filter),
                    Inventory.barcode.ilike(search_filter),
                    Inventory.manufacturer_part_number.ilike(search_filter),
                    code_matches(Inventory.manufacturer_part_number, search),
                    code_matches(Inventory.barcode, search),
                    Inventory.description.ilike(search_filter)
                )
            )
        
        if category:
            query = query.filter(Inventory.category == category)
        
        # Apply pagination
        _total = query.count()
        _pages = max(1, (_total + int(per_page) - 1) // int(per_page))
        _items = query.offset((int(page) - 1) * int(per_page)).limit(int(per_page)).all()
        class _Pg:
            pass
        pagination = _Pg()
        pagination.items = _items
        pagination.page = int(page)
        pagination.per_page = int(per_page)
        pagination.total = _total
        pagination.pages = _pages
        pagination.has_next = int(page) < _pages
        pagination.has_prev = int(page) > 1
        
        inventory_items = pagination.items
        movement_totals = get_inventory_movement_totals(db, inventory_items)
        items_data = [
            inventory_item_to_dict(item, movement_totals)
            for item in inventory_items
        ]
        
        return _json({
            'items': items_data,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }, 200)
        
    except Exception as e:
        logger.error(f"Error fetching inventory: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.post('/inventory')
async def create_inventory_item(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'inventory_manager']))):
    """Create a new inventory item"""
    try:
        image_path = None
        data, image_file = await _inventory_form_or_json(request)
        if not data:
            return _json({'error': 'No data provided'}, 400)
        if image_file:
            try:
                image_path = save_uploaded_file(image_file)
            except ValueError as e:
                return _json({'error': str(e)}, 400)
        
        # Validate input data
        validation_errors = validate_inventory_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)
        
        # Extract and clean data
        name = str(data.get('name')).strip()
        category = str(data.get('category')).strip()
        barcode = clean_optional_text(data.get('barcode'))
        manufacturer_part_number = clean_optional_text(data.get('manufacturer_part_number'))
        quantity = int(data.get('quantity', 0))
        description = str(data.get('description', '')).strip() if data.get('description') else None
        location = str(data.get('location', '')).strip() if data.get('location') else None
        reorder_level = int(data.get('reorder_level', 5))

        code_error = ensure_unique_inventory_codes(
            db,
            barcode=barcode,
            manufacturer_part_number=manufacturer_part_number
        )
        if code_error:
            return _json({'error': code_error}, 400)
        
        # Create inventory item
        try:
            inventory_item = Inventory(
                name=name,
                category=category,
                barcode=barcode,
                manufacturer_part_number=manufacturer_part_number,
                quantity=max(0, quantity),
                reserved=0,
                price=float(data.get('price') or 0),
                description=description,
                location=location,
                reorder_level=reorder_level,
                min_level=int(data['min_level']) if data.get('min_level') not in (None, '') else None,
                max_level=int(data['max_level']) if data.get('max_level') not in (None, '') else None,
                alternate_codes=data.get('alternate_codes'),
                pending_purchase=bool(data.get('pending_purchase', False)),
                image_path=image_path,
            )
            db.add(inventory_item)
            db.flush()
            if not inventory_item.part_number:
                inventory_item.part_number = inventory_item.generate_part_number()
            db.commit()
            
            logger.info(f"Inventory item created successfully: ID {inventory_item.id}")
            
            return _json({
                'message': 'Inventory item created successfully',
                'item': inventory_item_detail_to_dict(db, inventory_item)
            }, 201)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating inventory item: {e}")
            status = 400 if isinstance(e, IntegrityError) else 500
            return _json({'error': inventory_database_error_message(e)}), status
            
    except Exception as e:
        logger.error(f"Unexpected error creating inventory item: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/inventory/by-category')
def get_inventory_by_category(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get inventory items grouped by category with pagination for each category"""
    try:
        # Get pagination parameters
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 50))
        category = request.query_params.get('category', '').strip()
        
        # Limit per_page to prevent excessive memory usage
        per_page = min(per_page, 200)
        
        # Get search parameters
        search = request.query_params.get('search', '').strip()
        
        if not category:
            return _json({'error': 'Category parameter is required'}, 400)
        
        # Build query for specific category
        query = db.query(Inventory).filter(Inventory.category == category)
        
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    Inventory.name.ilike(search_filter),
                    Inventory.part_number.ilike(search_filter),
                    Inventory.barcode.ilike(search_filter),
                    Inventory.manufacturer_part_number.ilike(search_filter),
                    code_matches(Inventory.manufacturer_part_number, search),
                    code_matches(Inventory.barcode, search),
                    Inventory.description.ilike(search_filter),
                    Inventory.location.ilike(search_filter),
                    Inventory.category.ilike(search_filter)
                )
            )
        
        # Apply pagination
        _total = query.count()
        _pages = max(1, (_total + int(per_page) - 1) // int(per_page))
        _items = query.offset((int(page) - 1) * int(per_page)).limit(int(per_page)).all()
        class _Pg:
            pass
        pagination = _Pg()
        pagination.items = _items
        pagination.page = int(page)
        pagination.per_page = int(per_page)
        pagination.total = _total
        pagination.pages = _pages
        pagination.has_next = int(page) < _pages
        pagination.has_prev = int(page) > 1
        
        inventory_items = pagination.items
        movement_totals = get_inventory_movement_totals(db, inventory_items)
        items_data = [
            inventory_item_to_dict(item, movement_totals)
            for item in inventory_items
        ]
        
        return _json({
            'items': items_data,
            'category': category,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }, 200)
        
    except Exception as e:
        logger.error(f"Error fetching inventory by category: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/inventory/categories')
def get_inventory_categories(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get distinct category names that exist in inventory (for grid loading)"""
    try:
        distinct = db.query(Inventory.category).distinct().order_by(Inventory.category).all()
        categories = [row[0] for row in distinct if row[0]]
        return _json({'categories': categories}, 200)
    except Exception as e:
        logger.error(f"Error fetching inventory categories: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.post('/inventory/check-stock')
def check_inventory_stock(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(get_current_user)):
    """Check if items have sufficient stock"""
    try:
        data = body
        if not data or 'items' not in data:
            return _json({'error': 'No items provided'}, 400)
        
        items = data['items']
        insufficient_items = []
        available_items = []
        
        for item_data in items:
            product_name = item_data.get('product_name', '').strip()
            part_number = item_data.get('part_number', '').strip()
            quantity = int(item_data.get('quantity', 0))
            
            if not product_name or quantity <= 0:
                continue
            
            # Find inventory item by part number first (most accurate)
            inventory_item = None
            if part_number:
                inventory_item = db.query(Inventory).filter_by(part_number=part_number).first()
            
            # If not found by part number, try by name
            if not inventory_item:
                inventory_item = db.query(Inventory).filter(
                    Inventory.name.ilike(f"%{product_name}%")
                ).first()
            
            # If still not found, try by description
            if not inventory_item:
                inventory_item = db.query(Inventory).filter(
                    Inventory.description.ilike(f"%{product_name}%")
                ).first()
            
            if inventory_item:
                # Always add to available_items for deduction, regardless of stock level
                available_items.append({
                    'product_name': product_name,
                    'part_number': part_number,
                    'quantity': quantity,
                    'inventory_id': inventory_item.id,
                    'available_quantity': inventory_item.quantity,
                    'inventory_part_number': inventory_item.part_number,
                    'insufficient_stock': inventory_item.quantity < quantity
                })
            else:
                insufficient_items.append({
                    'product_name': product_name,
                    'part_number': part_number,
                    'quantity': quantity,
                    'available_quantity': 0,
                    'inventory_id': None,
                    'inventory_part_number': None
                })
        
        return _json({
            'insufficient_items': insufficient_items,
            'available_items': available_items
        }, 200)
        
    except Exception as e:
        logger.error(f"Error checking inventory stock: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.post('/inventory/deduct-items')
def deduct_inventory_items(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'inventory_manager']))):
    """Deduct items from inventory"""
    try:
        data = body
        if not data or 'items' not in data:
            return _json({'error': 'No items provided'}, 400)
        
        items = data['items']
        deducted_items = []
        failed_items = []
        
        for item_data in items:
            product_name = item_data.get('product_name', '').strip()
            part_number = item_data.get('part_number', '').strip()
            quantity = int(item_data.get('quantity', 0))
            inventory_id = item_data.get('inventory_id')
            
            if not product_name or quantity <= 0:
                continue
            
            try:
                if inventory_id:
                    inventory_item = db.get(Inventory, inventory_id)
                else:
                    # Find by part number first (most accurate)
                    inventory_item = None
                    if part_number:
                        inventory_item = db.query(Inventory).filter_by(part_number=part_number).first()
                    
                    # If not found by part number, try by name
                    if not inventory_item:
                        inventory_item = db.query(Inventory).filter(
                            Inventory.name.ilike(f"%{product_name}%")
                        ).first()
                    
                    # If still not found, try by description
                    if not inventory_item:
                        inventory_item = db.query(Inventory).filter(
                            Inventory.description.ilike(f"%{product_name}%")
                        ).first()
                    
                    # If still not found, try exact name match
                    if not inventory_item:
                        inventory_item = db.query(Inventory).filter_by(name=product_name).first()
                
                if inventory_item:
                    # Store previous quantity for transaction logging
                    previous_quantity = inventory_item.quantity
                    
                    # Deduct the quantity (allow negative stock)
                    inventory_item.quantity -= quantity
                    inventory_item.updated_at = datetime.utcnow()
                    
                    # Log the transaction
                    user_id = current_user.id if current_user else None
                    log_issue_out(db, 
                        inventory_id=inventory_item.id,
                        quantity=quantity,
                        previous_quantity=previous_quantity,
                        new_quantity=inventory_item.quantity,
                        reference_description=f"Manual deduction - {product_name}",
                        created_by=user_id,
                        notes=data.get('notes')
                    )
                    
                    deducted_items.append({
                        'product_name': product_name,
                        'part_number': part_number,
                        'quantity': quantity,
                        'inventory_id': inventory_item.id,
                        'inventory_part_number': inventory_item.part_number,
                        'new_quantity': inventory_item.quantity
                    })
                    
                    logger.info(f"Successfully deducted {quantity} units of {product_name} from inventory. New quantity: {inventory_item.quantity}")
                else:
                    failed_items.append({
                        'product_name': product_name,
                        'quantity': quantity,
                        'reason': 'Item not found'
                    })
                    
            except Exception as e:
                logger.error(f"Error deducting {product_name}: {e}")
                failed_items.append({
                    'product_name': product_name,
                    'quantity': quantity,
                    'reason': str(e)
                })
        
        # Commit all changes
        db.commit()
        
        return _json({
            'deducted_items': deducted_items,
            'failed_items': failed_items,
            'message': f'Successfully deducted {len(deducted_items)} items'
        }, 200)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deducting inventory items: {e}")
        return _json({'error': 'Internal server error'}, 500) 

@router.get('/inventory/reorder-suggestions')
def reorder_suggestions(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'inventory_manager', 'accountant']))):
    """Parts at/below min (reorder) level that can auto-draft POs."""
    items = db.query(Inventory).order_by(Inventory.name).all()
    suggestions = []
    for item in items:
        min_lvl = item.effective_min_level if hasattr(item, 'effective_min_level') else int(item.reorder_level or 0)
        available = int(item.quantity or 0) - int(getattr(item, 'reserved', 0) or 0)
        if available > min_lvl:
            continue
        reorder_qty = int(getattr(item, 'reorder_quantity', 10) or 10)
        max_lvl = getattr(item, 'max_level', None)
        if max_lvl is not None:
            reorder_qty = max(reorder_qty, int(max_lvl) - available)
        suggestions.append({
            **inventory_item_to_dict(item),
            'suggested_order_qty': max(1, reorder_qty),
            'below_min_by': max(0, min_lvl - available),
        })
    return _json({'suggestions': suggestions, 'count': len(suggestions)}, 200)


@router.post('/inventory/reorder-suggestions/draft-pos')
@idempotent_create
def draft_pos_from_reorder(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(['admin', 'inventory_manager', 'accountant'])),
):
    """Auto-draft POs for selected reorder suggestions (requires vendor_id)."""
    from datetime import date as date_cls
    from decimal import Decimal

    data = body or {}
    vendor_id = data.get('vendor_id')
    if not vendor_id:
        return _json({'error': 'vendor_id is required'}, 400)
    vendor = db.get(Vendor, int(vendor_id))
    if not vendor:
        return _json({'error': 'Vendor not found'}, 404)

    item_ids = data.get('inventory_ids')
    if item_ids:
        items = db.query(Inventory).filter(Inventory.id.in_([int(i) for i in item_ids])).all()
    else:
        # All below min
        all_items = db.query(Inventory).all()
        items = [
            i for i in all_items
            if (int(i.quantity or 0) - int(getattr(i, 'reserved', 0) or 0))
            <= (i.effective_min_level if hasattr(i, 'effective_min_level') else int(i.reorder_level or 0))
        ]

    created = []
    for item in items:
        available = int(item.quantity or 0) - int(getattr(item, 'reserved', 0) or 0)
        qty = int(getattr(item, 'reorder_quantity', 10) or 10)
        max_lvl = getattr(item, 'max_level', None)
        if max_lvl is not None:
            qty = max(qty, int(max_lvl) - available)
        qty = max(1, qty)
        rate = Decimal(str(getattr(item, 'avg_cost', 0) or item.price or 0))
        po = PurchaseOrder(
            vendor_id=vendor.id,
            inventory_id=item.id,
            date=date_cls.today(),
            invoice_no=f"DRAFT-{item.part_number}-{datetime.utcnow().strftime('%H%M%S')}",
            item_name=item.name,
            quantity=qty,
            qty_received=0,
            rate=rate,
            amount=rate * qty,
            remarks=f"Auto-draft reorder (available {available})",
            status='draft',
            created_by_user=current_user.username if current_user else None,
        )
        db.add(po)
        db.flush()
        created.append(po.to_dict())
    db.commit()
    return _json({'message': f'Drafted {len(created)} POs', 'purchase_orders': created}, 201)


@router.post('/inventory/adjust')
def adjust_inventory_stock(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(['admin', 'inventory_manager'])),
):
    """Stock adjustment — requires adjust_stock permission, reason, and evidence."""
    from app.foundation.overrides import require_override
    from app.stock import StockError, adjust as stock_adjust

    data = body or {}
    item_id = data.get('inventory_id') or data.get('item_id')
    if not item_id:
        return _json({'error': 'inventory_id is required'}, 400)
    item = db.get(Inventory, int(item_id))
    if not item:
        return _json({'error': 'Inventory item not found'}, 404)
    try:
        delta = int(data.get('delta') if data.get('delta') is not None else data.get('quantity_change', 0))
    except (TypeError, ValueError):
        return _json({'error': 'delta must be an integer'}, 400)

    reason = data.get('reason')
    evidence = data.get('evidence_path') or data.get('attachment_path')
    try:
        require_override(db, current_user, 'stock_adjustment', reason=reason)
    except Exception as exc:
        from fastapi import HTTPException
        if isinstance(exc, HTTPException):
            detail = exc.detail if isinstance(exc.detail, dict) else {'error': str(exc.detail)}
            return _json(detail, exc.status_code)
        raise

    try:
        txn = stock_adjust(
            db,
            item=item,
            delta=delta,
            reason=reason,
            evidence_path=evidence,
            created_by=current_user.id if current_user else None,
            notes=data.get('notes'),
        )
        db.commit()
        return _json({'message': 'Stock adjusted', 'item': inventory_item_to_dict(item), 'movement': txn.to_dict()}, 200)
    except StockError as exc:
        db.rollback()
        return _json({'error': str(exc)}, 400)
    except Exception as e:
        db.rollback()
        logger.error(f"adjust stock failed: {e}")
        return _json({'error': 'Failed to adjust stock'}, 500)


@router.post('/inventory/pending-item')
@idempotent_create
def create_pending_purchase_item(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(['admin', 'inventory_manager', 'accountant'])),
):
    """Inline add-new-item for job card: zero stock, flagged pending purchase."""
    data = body or {}
    name = (data.get('name') or data.get('description') or '').strip()
    if not name:
        return _json({'error': 'name is required'}, 400)
    category = (data.get('category') or 'Pending Purchase').strip()
    barcode = clean_optional_text(data.get('barcode'))
    mfr = clean_optional_text(data.get('manufacturer_part_number') or data.get('part_number'))
    code_error = ensure_unique_inventory_codes(db, barcode=barcode, manufacturer_part_number=mfr)
    if code_error:
        return _json({'error': code_error}, 400)

    item = Inventory(
        name=name,
        category=category,
        barcode=barcode,
        manufacturer_part_number=mfr,
        quantity=0,
        reserved=0,
        price=float(data.get('price') or 0),
        description=data.get('description'),
        location=data.get('location'),
        reorder_level=int(data.get('reorder_level') or data.get('min_level') or 0),
        min_level=data.get('min_level'),
        max_level=data.get('max_level'),
        pending_purchase=True,
        alternate_codes=data.get('alternate_codes'),
    )
    item.part_number = item.generate_part_number()
    db.add(item)
    db.commit()
    db.refresh(item)
    return _json(
        {
            'message': 'Pending purchase item created',
            'item': inventory_item_to_dict(item),
            'pending_purchase': True,
        },
        201,
    )


@router.get('/inventory/label/{item_id:int}')
def inventory_label_data(item_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Payload for barcode label printing (name, part #, barcode)."""
    item = db.get(Inventory, item_id)
    if not item:
        return _json({'error': 'Inventory item not found'}, 404)
    return _json(
        {
            'id': item.id,
            'name': item.name,
            'part_number': item.part_number,
            'barcode': item.barcode or item.part_number,
            'manufacturer_part_number': item.manufacturer_part_number,
            'location': item.location,
            'print': {
                'title': item.name,
                'subtitle': item.part_number,
                'barcode_value': item.barcode or item.part_number,
            },
        },
        200,
    )


@router.get('/inventory/lookup')
def lookup_inventory_by_code(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Find one inventory item by barcode, manufacturer part number, or internal part number."""
    try:
        code = clean_optional_text(request.query_params.get('code'))
        if not code:
            return _json({'error': 'Code is required'}, 400)

        item = find_inventory_item_by_code(db, code)
        if not item:
            # Unknown barcode → prefill create-item form for scanner UX (200 so clients can branch)
            return _json(
                {
                    'found': False,
                    'create_prefill': {
                        'barcode': code,
                        'manufacturer_part_number': code,
                        'name': '',
                        'category': '',
                        'quantity': 0,
                    },
                },
                200,
            )

        return _json({'found': True, 'item': inventory_item_detail_to_dict(db, item)}, 200)

    except Exception as e:
        logger.error(f"Error looking up inventory item by code: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/inventory/low-stock')
def get_low_stock_items(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get inventory items that are below reorder level, separated by urgency"""
    try:
        # Get items where quantity is less than or equal to reorder_level
        low_stock_items = db.query(Inventory).filter(Inventory.quantity <= Inventory.reorder_level).all()
        movement_totals = get_inventory_movement_totals(db, low_stock_items)
        
        urgent_items = []  # Negative values (urgent)
        low_stock_items_data = []  # Regular low stock items
        
        for item in low_stock_items:
            item_data = inventory_item_to_dict(item, movement_totals)
            
            # Separate negative values (urgent) from regular low stock
            if item.quantity < 0:
                item_data['stock_status'] = 'URGENT - Negative Stock'
                item_data['urgency_level'] = 'critical'
                urgent_items.append(item_data)
            elif item.quantity == 0:
                item_data['stock_status'] = 'Out of Stock'
                item_data['urgency_level'] = 'high'
                low_stock_items_data.append(item_data)
            else:
                item_data['stock_status'] = 'Low Stock'
                item_data['urgency_level'] = 'medium'
                low_stock_items_data.append(item_data)
        
        return _json({
            'urgent_items': urgent_items,
            'low_stock_items': low_stock_items_data
        }, 200)
        
    except Exception as e:
        logger.error(f"Error fetching low stock items: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.post('/inventory/receive')
def receive_inventory_by_code(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'inventory_manager']))):
    """Receive stock by scanned barcode or manufacturer/internal part number."""
    try:
        data = body or {}
        code = clean_optional_text(data.get('code'))
        quantity_to_add = int(data.get('quantity', 0))
        notes = clean_optional_text(data.get('notes'))

        if not code:
            return _json({'error': 'Barcode or part number is required'}, 400)

        if quantity_to_add <= 0:
            return _json({'error': 'Quantity must be greater than 0'}, 400)

        inventory_item = find_inventory_item_by_code(db, code)
        if not inventory_item:
            return _json({'error': 'Inventory item not found for scanned code'}, 404)

        old_quantity = inventory_item.quantity
        inventory_item.quantity += quantity_to_add
        inventory_item.updated_at = datetime.utcnow()

        log_received(db, 
            inventory_id=inventory_item.id,
            quantity=quantity_to_add,
            previous_quantity=old_quantity,
            new_quantity=inventory_item.quantity,
            reference_description=f"Inventory received by code scan - {inventory_item.name}",
            created_by=current_user.id if current_user else None,
            notes=notes or f"Scanned code: {code}"
        )

        db.commit()

        return _json({
            'message': 'Inventory received successfully',
            'product_id': inventory_item.id,
            'product_name': inventory_item.name,
            'code': code,
            'quantity_added': quantity_to_add,
            'old_quantity': old_quantity,
            'new_quantity': inventory_item.quantity,
            'item': inventory_item_detail_to_dict(db, inventory_item)
        }, 200)

    except ValueError as e:
        return _json({'error': f'Invalid quantity value: {str(e)}'}, 400)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error receiving inventory by code: {e}")
        return _json({'error': 'Database error occurred'}, 500)
    except Exception as e:
        db.rollback()
        logger.error(f"Error receiving inventory by code: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.post('/inventory/restock')
def restock_inventory(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'inventory_manager']))):
    """Restock inventory items by increasing quantity"""
    try:
        data = body
        if not data:
            return _json({'error': 'No data provided'}, 400)
        
        # Validate required fields
        if 'product_id' not in data or 'quantity' not in data:
            return _json({'error': 'Product ID and quantity are required'}, 400)
        
        product_id = data.get('product_id')
        quantity_to_add = int(data.get('quantity', 0))
        notes = data.get('notes', '')
        
        # Validate quantity
        if quantity_to_add <= 0:
            return _json({'error': 'Quantity must be greater than 0'}, 400)
        
        # Find the inventory item
        inventory_item = db.get(Inventory, product_id)
        if not inventory_item:
            return _json({'error': 'Product not found'}, 404)
        
        # Store old quantity for logging
        old_quantity = inventory_item.quantity
        
        # Increase the quantity
        inventory_item.quantity += quantity_to_add
        
        # Update the updated_at timestamp
        inventory_item.updated_at = datetime.utcnow()
        
        # Log the restock transaction
        user_id = current_user.id if current_user else None
        log_received(db, 
            inventory_id=inventory_item.id,
            quantity=quantity_to_add,
            previous_quantity=old_quantity,
            new_quantity=inventory_item.quantity,
            reference_description=f"Inventory restock - {inventory_item.name}",
            created_by=user_id,
            notes=notes
        )
        
        # Log the restock operation
        logger.info(f"Restocked {quantity_to_add} units of {inventory_item.name} (ID: {product_id}). "
                   f"Old quantity: {old_quantity}, New quantity: {inventory_item.quantity}. "
                   f"Notes: {notes}")
        
        # Commit the changes
        db.commit()
        
        return _json({
            'message': 'Inventory restocked successfully',
            'product_id': product_id,
            'product_name': inventory_item.name,
            'quantity_added': quantity_to_add,
            'old_quantity': old_quantity,
            'new_quantity': inventory_item.quantity,
            'notes': notes,
            'item': inventory_item_detail_to_dict(db, inventory_item)
        }, 200)
        
    except ValueError as e:
        return _json({'error': f'Invalid quantity value: {str(e)}'}, 400)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during restock: {e}")
        return _json({'error': 'Database error occurred'}, 500)
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during restock: {e}")
        return _json({'error': 'Internal server error'}, 500)


# ===== INVENTORY TRANSACTION HISTORY =====

@router.get('/inventory/search')
def search_inventory(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Search inventory items"""
    try:
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return _json({'error': 'Search query is required'}, 400)
        
        # Cap the result set. A short common term used to match every row and
        # ship the whole table in one response; the client shows a "refine your
        # search" hint when total_count exceeds what was returned.
        limit = min(int(request.query_params.get('limit', 200)), 500)

        search_query = db.query(Inventory).filter(
            or_(
                Inventory.part_number.ilike(f'%{query}%'),
                Inventory.barcode.ilike(f'%{query}%'),
                Inventory.manufacturer_part_number.ilike(f'%{query}%'),
                code_matches(Inventory.manufacturer_part_number, query),
                code_matches(Inventory.barcode, query),
                Inventory.name.ilike(f'%{query}%'),
                Inventory.description.ilike(f'%{query}%'),
                Inventory.location.ilike(f'%{query}%'),
                Inventory.category.ilike(f'%{query}%')
            )
        )
        total_count = search_query.count()
        search_results = search_query.order_by(Inventory.name).limit(limit).all()

        movement_totals = get_inventory_movement_totals(db, search_results)
        items_data = [
            inventory_item_to_dict(item, movement_totals)
            for item in search_results
        ]
        
        return _json({
            'query': query,
            'results': items_data,
            'count': len(items_data)
        }, 200)
        
    except Exception as e:
        logger.error(f"Error searching inventory: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/inventory/search-grouped')
def search_inventory_grouped(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Search inventory items and return results grouped by category"""
    try:
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return _json({'error': 'Search query is required'}, 400)
        
        # Cap the result set. A short common term used to match every row and
        # ship the whole table in one response; the client shows a "refine your
        # search" hint when total_count exceeds what was returned.
        limit = min(int(request.query_params.get('limit', 200)), 500)

        search_query = db.query(Inventory).filter(
            or_(
                Inventory.part_number.ilike(f'%{query}%'),
                Inventory.barcode.ilike(f'%{query}%'),
                Inventory.manufacturer_part_number.ilike(f'%{query}%'),
                code_matches(Inventory.manufacturer_part_number, query),
                code_matches(Inventory.barcode, query),
                Inventory.name.ilike(f'%{query}%'),
                Inventory.description.ilike(f'%{query}%'),
                Inventory.location.ilike(f'%{query}%'),
                Inventory.category.ilike(f'%{query}%')
            )
        )
        total_count = search_query.count()
        search_results = search_query.order_by(Inventory.name).limit(limit).all()

        movement_totals = get_inventory_movement_totals(db, search_results)

        # Group results by category
        grouped_results = {}
        for item in search_results:
            category = item.category
            if category not in grouped_results:
                grouped_results[category] = []
            
            grouped_results[category].append(
                inventory_item_to_dict(item, movement_totals)
            )
        
        payload = {
            'query': query,
            'results': grouped_results,
            'total_count': total_count,
            'returned_count': len(search_results),
            'truncated': total_count > len(search_results),
            'category_count': len(grouped_results)
        }

        # Nothing matched. Offer a corrected spelling and the nearest items,
        # which between them cover a typo in the query and a typo in the data.
        if total_count == 0:
            corpus = [row[0] for row in db.query(Inventory.name).all()]
            payload.update(suggestions_for(query, corpus))

        return _json(payload, 200)
        
    except Exception as e:
        logger.error(f"Error searching inventory grouped: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/inventory/stats')
def get_inventory_stats(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get inventory statistics"""
    try:
        total_items = db.query(Inventory).count()
        low_stock_items = db.query(Inventory).filter(Inventory.quantity < 10).count()
        
        # Category breakdown
        category_stats = db.query(
            Inventory.category,
            func.count(Inventory.id).label('count')
        ).group_by(Inventory.category).all()
        
        category_data = []
        for stat in category_stats:
            category_data.append({
                'category': stat.category,
                'count': stat.count
            })
        
        return _json({
            'total_items': total_items,
            'low_stock_items': low_stock_items,
            'categories': category_data
        }, 200)
        
    except Exception as e:
        logger.error(f"Error getting inventory stats: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/inventory/transactions')
def get_inventory_transactions_route(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get inventory transaction history with optional filters"""
    try:
        # Get query parameters
        inventory_id = (
            int(request.query_params["inventory_id"])
            if "inventory_id" in request.query_params
            else None
        )
        transaction_type = request.query_params.get("transaction_type")
        repair_order_id = (
            int(request.query_params["repair_order_id"])
            if "repair_order_id" in request.query_params
            else None
        )
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 50))
        
        # Limit per_page to prevent excessive memory usage
        per_page = min(per_page, 200)
        
        # Parse date filters
        date_from_obj = None
        date_to_obj = None
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            except ValueError:
                return _json({'error': 'Invalid date_from format. Use YYYY-MM-DD'}, 400)
        
        if date_to:
            try:
                # Add 1 day to include the entire day
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
            except ValueError:
                return _json({'error': 'Invalid date_to format. Use YYYY-MM-DD'}, 400)
        
        # Validate transaction type
        valid_types = ['issue_out', 'received', 'adjustment']
        if transaction_type and transaction_type not in valid_types:
            return _json({'error': f'Invalid transaction_type. Valid types: {valid_types}'}, 400)
        
        # Get transactions using utility function
        transactions, pagination_info = get_inventory_transactions(db, 
            inventory_id=inventory_id,
            transaction_type=transaction_type,
            repair_order_id=repair_order_id,
            date_from=date_from_obj,
            date_to=date_to_obj,
            page=page,
            per_page=per_page
        )
        
        return _json({
            'transactions': transactions,
            'pagination': pagination_info
        }, 200)
        
    except Exception as e:
        logger.error(f"Error fetching inventory transactions: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.get('/inventory/transactions/{transaction_id:int}')
def get_inventory_transaction_detail(transaction_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get details of a specific inventory transaction"""
    try:
        transaction = db.get(InventoryTransaction, transaction_id)
        
        if not transaction:
            return _json({'error': 'Transaction not found'}, 404)
        
        return _json(transaction.to_dict())
        
    except Exception as e:
        logger.error(f"Error fetching inventory transaction {transaction_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.put('/inventory/{item_id:int}')
async def update_inventory_item(item_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'inventory_manager']))):
    """Update an existing inventory item"""
    from app.foundation.versioning import bump_version, check_version, extract_version

    try:
        if not item_id or item_id <= 0:
            return _json({'error': 'Invalid item ID'}, 400)
        
        # Find the inventory item first
        item = db.get(Inventory, item_id)
        if not item:
            return _json({'error': 'Inventory item not found'}, 404)

        data, image_file = await _inventory_form_or_json(request)
        if not data:
            return _json({'error': 'No data provided'}, 400)
        check_version(item, extract_version(data))

        image_path = item.image_path
        if str(data.get('remove_image', '')).lower() == 'true':
            if item.image_path:
                old_image_path = os.path.join('static', item.image_path)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            image_path = None
        elif image_file:
            try:
                if item.image_path:
                    old_image_path = os.path.join('static', item.image_path)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                image_path = save_uploaded_file(image_file)
            except ValueError as e:
                return _json({'error': str(e)}, 400)
        
        # Validate input data
        validation_errors = validate_inventory_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)
        
        # Extract and clean data
        name = str(data.get('name')).strip()
        category = str(data.get('category')).strip()
        barcode = clean_optional_text(data.get('barcode'))
        manufacturer_part_number = clean_optional_text(data.get('manufacturer_part_number'))
        description = str(data.get('description', '')).strip() if data.get('description') else None
        location = str(data.get('location', '')).strip() if data.get('location') else None
        reorder_level = int(data.get('reorder_level', 5))

        # No direct stock/cost edits — use /inventory/adjust or PO receive.
        if 'quantity' in data and int(data.get('quantity', item.quantity)) != int(item.quantity or 0):
            return _json(
                {
                    'error': 'Direct quantity edits are not allowed. Use POST /api/inventory/adjust '
                    '(reason + evidence + adjust_stock) or PO receive.',
                },
                400,
            )
        if 'avg_cost' in data:
            return _json({'error': 'avg_cost updates only on PO GRN'}, 400)

        code_error = ensure_unique_inventory_codes(
            db,
            barcode=barcode,
            manufacturer_part_number=manufacturer_part_number,
            item_id=item.id
        )
        if code_error:
            return _json({'error': code_error}, 400)

        # Update inventory item (metadata only)
        try:
            item.name = name
            item.category = category
            item.barcode = barcode
            item.manufacturer_part_number = manufacturer_part_number
            item.description = description
            item.location = location
            item.reorder_level = reorder_level
            if data.get('min_level') is not None:
                item.min_level = int(data['min_level'])
            if data.get('max_level') is not None:
                item.max_level = int(data['max_level'])
            if data.get('reorder_quantity') is not None:
                item.reorder_quantity = int(data['reorder_quantity'])
            if data.get('superseded_by_id') is not None:
                item.superseded_by_id = int(data['superseded_by_id']) or None
            if 'alternate_codes' in data:
                item.alternate_codes = data.get('alternate_codes')
            if data.get('price') is not None:
                from app.foundation.context import get_reason
                if not (get_reason() or data.get('reason')):
                    return _json(
                        {'error': 'reason is required for price edits', 'require_reason': True},
                        400,
                    )
                item.price = float(data['price'])
            item.image_path = image_path
            bump_version(item)

            # Log adjustment if quantity changed
            if old_quantity != new_quantity:
                from app.foundation.overrides import require_override

                require_override(
                    db,
                    current_user,
                    "stock_adjustment",
                    reason=data.get("reason") or request.headers.get("X-Audit-Reason"),
                )
                quantity_change = new_quantity - old_quantity
                user_id = current_user.id if current_user else None
                log_adjustment(
                    db,
                    inventory_id=item.id,
                    quantity_change=quantity_change,
                    previous_quantity=old_quantity,
                    new_quantity=new_quantity,
                    reference_description=f"Manual quantity adjustment - {item.name}",
                    created_by=user_id,
                    notes=f"Quantity changed from {old_quantity} to {new_quantity}",
                )

            db.commit()

            logger.info(f"Inventory item updated successfully: ID {item.id}")

            return _json({
                'message': 'Inventory item updated successfully',
                'item': inventory_item_detail_to_dict(db, item)
            }, 200)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating inventory item {item_id}: {e}")
            status = 400 if isinstance(e, IntegrityError) else 500
            return _json({'error': inventory_database_error_message(e)}), status
            
    except Exception as e:
        logger.error(f"Unexpected error updating inventory item {item_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.delete('/inventory/{item_id:int}')
def delete_inventory_item(item_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'inventory_manager']))):
    """Delete an inventory item"""
    try:
        if not item_id or item_id <= 0:
            return _json({'error': 'Invalid item ID'}, 400)
        
        # Find the inventory item
        item = db.get(Inventory, item_id)
        if not item:
            return _json({'error': 'Inventory item not found'}, 404)
        
        # Delete inventory item
        try:
            # Nullify references in RepairOrderPart so history remains readable but unlinked
            db.query(RepairOrderPart).filter(RepairOrderPart.inventory_id == item_id).update({RepairOrderPart.inventory_id: None})
            
            # Delete related transactions
            db.query(InventoryTransaction).filter(InventoryTransaction.inventory_id == item_id).delete()
            
            db.delete(item)
            db.commit()
            
            logger.info(f"Inventory item deleted successfully: ID {item_id}")
            
            return _json({
                'message': 'Inventory item deleted successfully',
                'deleted_item_id': item_id
            }, 200)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting inventory item {item_id}: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Unexpected error deleting inventory item {item_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/inventory/{item_id:int}')
def get_inventory_item(item_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get specific inventory item by ID.
    Declared after static /inventory/* paths so names like 'transactions' are not captured.
    """
    try:
        if not item_id or item_id <= 0:
            return _json({'error': 'Invalid item ID'}, 400)

        item = db.get(Inventory, item_id)
        if not item:
            return _json({'error': 'Inventory item not found'}, 404)

        return _json(inventory_item_detail_to_dict(db, item), 200)

    except Exception as e:
        logger.error(f"Error fetching inventory item {item_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.get('/inventory/{item_id:int}/ledger')
def get_item_ledger(item_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Return date-wise in/out ledger used to back each inventory card Excel file."""
    try:
        if not item_id or item_id <= 0:
            return _json({'error': 'Invalid item ID'}, 400)

        item = db.get(Inventory, item_id)
        if not item:
            return _json({'error': 'Inventory item not found'}, 404)

        ledger = build_item_daily_ledger(db, item)
        return _json({
            'item': inventory_item_detail_to_dict(db, item),
            'daily_rows': ledger['daily_rows'],
            'transactions': ledger['transactions'],
            'movement_date': ledger['movement_date'],
        }, 200)

    except Exception as e:
        logger.error(f"Error building ledger for item {item_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)
@router.get('/inventory/{item_id:int}/transactions')
def get_item_transactions(item_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get transaction history for a specific inventory item"""
    try:
        # Verify item exists
        item = db.get(Inventory, item_id)
        if not item:
            return _json({'error': 'Inventory item not found'}, 404)
        
        # Get query parameters
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 50))
        per_page = min(per_page, 200)
        
        # Get transactions for this item
        transactions, pagination_info = get_inventory_transactions(db, 
            inventory_id=item_id,
            page=page,
            per_page=per_page
        )
        
        return _json({
            'item': {
                'id': item.id,
                'name': item.name,
                'part_number': item.part_number,
                'current_quantity': item.quantity
            },
            'transactions': transactions,
            'pagination': pagination_info
        }, 200)
        
    except Exception as e:
        logger.error(f"Error fetching transactions for item {item_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)


