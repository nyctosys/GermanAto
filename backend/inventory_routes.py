from flask import Blueprint, request, jsonify
from models import db, Inventory, InventoryTransaction
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo
import logging
import os
import uuid
from werkzeug.utils import secure_filename
from jwt_auth import login_required, role_required, admin_required
from inventory_transaction_utils import log_issue_out, log_received, log_adjustment, get_inventory_transactions

# Business day boundary for opening/closing rollover (matches frontend Asia/Karachi usage)
BUSINESS_TZ = ZoneInfo('Asia/Karachi')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

inventory_bp = Blueprint('inventory', __name__)

# Configuration for file uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Save uploaded file and return the relative path"""
    if not file or not file.filename:
        return None
    
    if not allowed_file(file.filename):
        raise ValueError("Invalid file type. Only image files are allowed.")
    
    # Generate unique filename
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    secure_name = secure_filename(unique_filename)
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Save file
    file_path = os.path.join(UPLOAD_FOLDER, secure_name)
    file.save(file_path)
    
    # Return relative path for database storage
    return f"uploads/{secure_name}"

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


def get_inventory_movement_totals(items, business_day=None):
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
            'closing_quantity': item.quantity,
            'movement_date': business_day.isoformat(),
        }
        for item in items
    }

    if not item_ids:
        return movement_totals

    transactions = InventoryTransaction.query.filter(
        InventoryTransaction.inventory_id.in_(item_ids),
        InventoryTransaction.created_at >= day_start,
        InventoryTransaction.created_at < day_end,
    ).all()

    for transaction in transactions:
        item_totals = movement_totals[transaction.inventory_id]
        inbound, outbound = classify_movement_quantity(transaction.quantity)
        item_totals['purchases_quantity'] += inbound
        item_totals['sales_quantity'] += outbound

    for item in items:
        item_totals = movement_totals[item.id]
        item_totals['opening_quantity'] = (
            item.quantity
            - item_totals['purchases_quantity']
            + item_totals['sales_quantity']
        )

    return movement_totals


def build_item_daily_ledger(item):
    """Build date-wise opening/in/out/closing rows for one inventory item.

    Walks every logged transaction chronologically so each day's closing becomes
    the next day's opening. Days with no movement are omitted unless needed for
    continuity from the earliest transaction through today.
    """
    business_today = get_business_now().date()
    transactions = (
        InventoryTransaction.query
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
                'closing': item.quantity,
            }],
            'transactions': [],
            'movement_date': business_today.isoformat(),
        }

    for current_date in sorted(grouped.keys()):
        day_transactions = grouped[current_date]
        opening = running_quantity
        inbound_total = 0
        outbound_total = 0

        for transaction in day_transactions:
            quantity = transaction.quantity or 0
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
                'in_quantity': inbound,
                'out_quantity': outbound,
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
            'closing': running_quantity,
        })

    if not daily_rows or daily_rows[-1]['date'] != business_today.isoformat():
        daily_rows.append({
            'date': business_today.isoformat(),
            'opening': running_quantity,
            'in_quantity': 0,
            'out_quantity': 0,
            'closing': running_quantity,
        })

    return {
        'daily_rows': daily_rows,
        'transactions': transaction_rows,
        'movement_date': business_today.isoformat(),
    }


def inventory_item_to_dict(item, movement_totals=None):
    item_data = {
        'id': item.id,
        'part_number': item.part_number,
        'barcode': item.barcode,
        'manufacturer_part_number': item.manufacturer_part_number,
        'name': item.name,
        'category': item.category,
        'quantity': item.quantity,
        'description': item.description,
        'location': item.location,
        'reorder_level': item.reorder_level,
        'image_path': item.image_path,
        'created_at': item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        'updated_at': item.updated_at.strftime("%Y-%m-%d %H:%M:%S")
    }

    if movement_totals and item.id in movement_totals:
        item_data.update(movement_totals[item.id])
    else:
        item_data['movement_date'] = get_business_now().date().isoformat()

    return item_data

def inventory_item_detail_to_dict(item, business_day=None):
    return inventory_item_to_dict(
        item,
        get_inventory_movement_totals([item], business_day=business_day)
    )

def find_inventory_item_by_code(code):
    code = clean_optional_text(code)
    if not code:
        return None

    return (
        Inventory.query.filter(Inventory.barcode == code).first()
        or Inventory.query.filter(Inventory.manufacturer_part_number == code).first()
        or Inventory.query.filter(Inventory.part_number == code).first()
    )

def ensure_unique_inventory_codes(barcode=None, manufacturer_part_number=None, item_id=None):
    if barcode:
        existing = Inventory.query.filter(Inventory.barcode == barcode)
        if item_id:
            existing = existing.filter(Inventory.id != item_id)
        if existing.first():
            return f"Barcode {barcode} is already assigned to another inventory item"

    if manufacturer_part_number:
        existing = Inventory.query.filter(
            Inventory.manufacturer_part_number == manufacturer_part_number
        )
        if item_id:
            existing = existing.filter(Inventory.id != item_id)
        if existing.first():
            return f"Manufacturer part number {manufacturer_part_number} is already assigned to another inventory item"

    return None

@inventory_bp.route('/inventory', methods=['GET'])
@login_required
def get_inventory(current_user=None):
    """Get inventory items with pagination"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Limit per_page to prevent excessive memory usage
        per_page = min(per_page, 200)
        
        # Get search parameters
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        
        # Build query
        query = Inventory.query
        
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                db.or_(
                    Inventory.name.ilike(search_filter),
                    Inventory.part_number.ilike(search_filter),
                    Inventory.barcode.ilike(search_filter),
                    Inventory.manufacturer_part_number.ilike(search_filter),
                    Inventory.description.ilike(search_filter)
                )
            )
        
        if category:
            query = query.filter(Inventory.category == category)
        
        # Apply pagination
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        inventory_items = pagination.items
        movement_totals = get_inventory_movement_totals(inventory_items)
        items_data = [
            inventory_item_to_dict(item, movement_totals)
            for item in inventory_items
        ]
        
        return jsonify({
            'items': items_data,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching inventory: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/by-category', methods=['GET'])
@login_required
def get_inventory_by_category(current_user=None):
    """Get inventory items grouped by category with pagination for each category"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        category = request.args.get('category', '').strip()
        
        # Limit per_page to prevent excessive memory usage
        per_page = min(per_page, 200)
        
        # Get search parameters
        search = request.args.get('search', '').strip()
        
        if not category:
            return jsonify({'error': 'Category parameter is required'}), 400
        
        # Build query for specific category
        query = Inventory.query.filter(Inventory.category == category)
        
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                db.or_(
                    Inventory.name.ilike(search_filter),
                    Inventory.part_number.ilike(search_filter),
                    Inventory.barcode.ilike(search_filter),
                    Inventory.manufacturer_part_number.ilike(search_filter),
                    Inventory.description.ilike(search_filter),
                    Inventory.location.ilike(search_filter),
                    Inventory.category.ilike(search_filter)
                )
            )
        
        # Apply pagination
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        inventory_items = pagination.items
        movement_totals = get_inventory_movement_totals(inventory_items)
        items_data = [
            inventory_item_to_dict(item, movement_totals)
            for item in inventory_items
        ]
        
        return jsonify({
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
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching inventory by category: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/<int:item_id>', methods=['GET'])
@login_required
def get_inventory_item(item_id, current_user=None):
    """Get specific inventory item by ID"""
    try:
        if not item_id or item_id <= 0:
            return jsonify({'error': 'Invalid item ID'}), 400
        
        item = Inventory.query.get(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        item_data = inventory_item_detail_to_dict(item)
        
        return jsonify(item_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching inventory item {item_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory', methods=['POST'])
@role_required(['admin', 'inventory_manager'])
def create_inventory_item(current_user=None):
    """Create a new inventory item"""
    try:
        # Initialize image_path to None
        image_path = None
        
        # Check if request is form data (with file upload) or JSON
        if request.form:
            # Handle form data with potential file upload
            data = request.form.to_dict()
            
            # Handle image upload
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename:
                    try:
                        image_path = save_uploaded_file(file)
                    except ValueError as e:
                        return jsonify({'error': str(e)}), 400
        else:
            # Handle JSON data (for API calls)
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
        
        # Validate input data
        validation_errors = validate_inventory_data(data)
        if validation_errors:
            return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
        
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
            barcode=barcode,
            manufacturer_part_number=manufacturer_part_number
        )
        if code_error:
            return jsonify({'error': code_error}), 400
        
        # Create inventory item
        try:
            inventory_item = Inventory(
                name=name,
                category=category,
                barcode=barcode,
                manufacturer_part_number=manufacturer_part_number,
                quantity=quantity,
                description=description,
                location=location,
                reorder_level=reorder_level,
                image_path=image_path
            )
            db.session.add(inventory_item)
            db.session.commit()
            
            logger.info(f"Inventory item created successfully: ID {inventory_item.id}")
            
            return jsonify({
                'message': 'Inventory item created successfully',
                'item': inventory_item_detail_to_dict(inventory_item)
            }), 201
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error creating inventory item: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error creating inventory item: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/<int:item_id>', methods=['PUT'])
@role_required(['admin', 'inventory_manager'])
def update_inventory_item(item_id, current_user=None):
    """Update an existing inventory item"""
    try:
        if not item_id or item_id <= 0:
            return jsonify({'error': 'Invalid item ID'}), 400
        
        # Find the inventory item first
        item = Inventory.query.get(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        # Check if request is form data (with file upload) or JSON
        if request.form:
            # Handle form data with potential file upload
            data = request.form.to_dict()
            logger.info(f"Update form data received: {data}")
            logger.info(f"remove_image in data: {'remove_image' in data}")
            if 'remove_image' in data:
                logger.info(f"remove_image value: {data['remove_image']}")
            
            # Handle image upload - prioritize remove_image flag over new upload
            image_path = item.image_path  # Keep existing image by default
            
            if 'remove_image' in data and data['remove_image'] == 'true':
                # Remove existing image (this takes priority)
                logger.info("Removing existing image")
                if item.image_path:
                    old_image_path = os.path.join('static', item.image_path)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                        logger.info(f"Deleted old image: {old_image_path}")
                image_path = None
            elif 'image' in request.files:
                file = request.files['image']
                if file and file.filename:
                    try:
                        # Delete old image if it exists
                        if item.image_path:
                            old_image_path = os.path.join('static', item.image_path)
                            if os.path.exists(old_image_path):
                                os.remove(old_image_path)
                        
                        image_path = save_uploaded_file(file)
                    except ValueError as e:
                        return jsonify({'error': str(e)}), 400
        else:
            # Handle JSON data (for API calls)
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            image_path = item.image_path  # Keep existing image for JSON updates
        
        # Validate input data
        validation_errors = validate_inventory_data(data)
        if validation_errors:
            return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
        
        # Extract and clean data
        name = str(data.get('name')).strip()
        category = str(data.get('category')).strip()
        barcode = clean_optional_text(data.get('barcode'))
        manufacturer_part_number = clean_optional_text(data.get('manufacturer_part_number'))
        new_quantity = int(data.get('quantity', 0))
        description = str(data.get('description', '')).strip() if data.get('description') else None
        location = str(data.get('location', '')).strip() if data.get('location') else None
        reorder_level = int(data.get('reorder_level', 5))

        code_error = ensure_unique_inventory_codes(
            barcode=barcode,
            manufacturer_part_number=manufacturer_part_number,
            item_id=item.id
        )
        if code_error:
            return jsonify({'error': code_error}), 400
        
        # Store old quantity for transaction logging
        old_quantity = item.quantity
        
        # Update inventory item
        try:
            item.name = name
            item.category = category
            item.barcode = barcode
            item.manufacturer_part_number = manufacturer_part_number
            item.quantity = new_quantity
            item.description = description
            item.location = location
            item.reorder_level = reorder_level
            item.image_path = image_path
            
            # Log adjustment if quantity changed
            if old_quantity != new_quantity:
                quantity_change = new_quantity - old_quantity
                user_id = current_user.id if current_user else None
                log_adjustment(
                    inventory_id=item.id,
                    quantity_change=quantity_change,
                    previous_quantity=old_quantity,
                    new_quantity=new_quantity,
                    reference_description=f"Manual quantity adjustment - {item.name}",
                    created_by=user_id,
                    notes=f"Quantity changed from {old_quantity} to {new_quantity}"
                )
            
            db.session.commit()
            
            logger.info(f"Inventory item updated successfully: ID {item.id}")
            
            return jsonify({
                'message': 'Inventory item updated successfully',
                'item': inventory_item_detail_to_dict(item)
            }), 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error updating inventory item {item_id}: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error updating inventory item {item_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/<int:item_id>', methods=['DELETE'])
@role_required(['admin', 'inventory_manager'])
def delete_inventory_item(item_id, current_user=None):
    """Delete an inventory item"""
    try:
        if not item_id or item_id <= 0:
            return jsonify({'error': 'Invalid item ID'}), 400
        
        # Find the inventory item
        item = Inventory.query.get(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        # Delete inventory item
        try:
            db.session.delete(item)
            db.session.commit()
            
            logger.info(f"Inventory item deleted successfully: ID {item_id}")
            
            return jsonify({
                'message': 'Inventory item deleted successfully',
                'deleted_item_id': item_id
            }), 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error deleting inventory item {item_id}: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error deleting inventory item {item_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/search', methods=['GET'])
@login_required
def search_inventory(current_user=None):
    """Search inventory items"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        # Search in part_number, name, description, location, and category
        search_results = Inventory.query.filter(
            db.or_(
                Inventory.part_number.ilike(f'%{query}%'),
                Inventory.barcode.ilike(f'%{query}%'),
                Inventory.manufacturer_part_number.ilike(f'%{query}%'),
                Inventory.name.ilike(f'%{query}%'),
                Inventory.description.ilike(f'%{query}%'),
                Inventory.location.ilike(f'%{query}%'),
                Inventory.category.ilike(f'%{query}%')
            )
        ).all()
        
        movement_totals = get_inventory_movement_totals(search_results)
        items_data = [
            inventory_item_to_dict(item, movement_totals)
            for item in search_results
        ]
        
        return jsonify({
            'query': query,
            'results': items_data,
            'count': len(items_data)
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching inventory: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/search-grouped', methods=['GET'])
@login_required
def search_inventory_grouped(current_user=None):
    """Search inventory items and return results grouped by category"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        # Search in part_number, name, description, location, and category
        search_results = Inventory.query.filter(
            db.or_(
                Inventory.part_number.ilike(f'%{query}%'),
                Inventory.barcode.ilike(f'%{query}%'),
                Inventory.manufacturer_part_number.ilike(f'%{query}%'),
                Inventory.name.ilike(f'%{query}%'),
                Inventory.description.ilike(f'%{query}%'),
                Inventory.location.ilike(f'%{query}%'),
                Inventory.category.ilike(f'%{query}%')
            )
        ).all()
        
        movement_totals = get_inventory_movement_totals(search_results)

        # Group results by category
        grouped_results = {}
        for item in search_results:
            category = item.category
            if category not in grouped_results:
                grouped_results[category] = []
            
            grouped_results[category].append(
                inventory_item_to_dict(item, movement_totals)
            )
        
        return jsonify({
            'query': query,
            'results': grouped_results,
            'total_count': len(search_results),
            'category_count': len(grouped_results)
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching inventory grouped: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/categories', methods=['GET'])
@login_required
def get_inventory_categories(current_user=None):
    """Get distinct category names that exist in inventory (for grid loading)"""
    try:
        distinct = db.session.query(Inventory.category).distinct().order_by(Inventory.category).all()
        categories = [row[0] for row in distinct if row[0]]
        return jsonify({'categories': categories}), 200
    except Exception as e:
        logger.error(f"Error fetching inventory categories: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/stats', methods=['GET'])
@login_required
def get_inventory_stats(current_user=None):
    """Get inventory statistics"""
    try:
        total_items = Inventory.query.count()
        low_stock_items = Inventory.query.filter(Inventory.quantity < 10).count()
        
        # Category breakdown
        category_stats = db.session.query(
            Inventory.category,
            db.func.count(Inventory.id).label('count')
        ).group_by(Inventory.category).all()
        
        category_data = []
        for stat in category_stats:
            category_data.append({
                'category': stat.category,
                'count': stat.count
            })
        
        return jsonify({
            'total_items': total_items,
            'low_stock_items': low_stock_items,
            'categories': category_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting inventory stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/low-stock', methods=['GET'])
@login_required
def get_low_stock_items(current_user=None):
    """Get inventory items that are below reorder level, separated by urgency"""
    try:
        # Get items where quantity is less than or equal to reorder_level
        low_stock_items = Inventory.query.filter(Inventory.quantity <= Inventory.reorder_level).all()
        movement_totals = get_inventory_movement_totals(low_stock_items)
        
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
        
        return jsonify({
            'urgent_items': urgent_items,
            'low_stock_items': low_stock_items_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching low stock items: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/lookup', methods=['GET'])
@login_required
def lookup_inventory_by_code(current_user=None):
    """Find one inventory item by barcode, manufacturer part number, or internal part number."""
    try:
        code = clean_optional_text(request.args.get('code'))
        if not code:
            return jsonify({'error': 'Code is required'}), 400

        item = find_inventory_item_by_code(code)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404

        return jsonify({'item': inventory_item_detail_to_dict(item)}), 200

    except Exception as e:
        logger.error(f"Error looking up inventory item by code: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/receive', methods=['POST'])
@role_required(['admin', 'inventory_manager'])
def receive_inventory_by_code(current_user=None):
    """Receive stock by scanned barcode or manufacturer/internal part number."""
    try:
        data = request.get_json() or {}
        code = clean_optional_text(data.get('code'))
        quantity_to_add = int(data.get('quantity', 0))
        notes = clean_optional_text(data.get('notes'))

        if not code:
            return jsonify({'error': 'Barcode or part number is required'}), 400

        if quantity_to_add <= 0:
            return jsonify({'error': 'Quantity must be greater than 0'}), 400

        inventory_item = find_inventory_item_by_code(code)
        if not inventory_item:
            return jsonify({'error': 'Inventory item not found for scanned code'}), 404

        old_quantity = inventory_item.quantity
        inventory_item.quantity += quantity_to_add
        inventory_item.updated_at = datetime.utcnow()

        log_received(
            inventory_id=inventory_item.id,
            quantity=quantity_to_add,
            previous_quantity=old_quantity,
            new_quantity=inventory_item.quantity,
            reference_description=f"Inventory received by code scan - {inventory_item.name}",
            created_by=current_user.id if current_user else None,
            notes=notes or f"Scanned code: {code}"
        )

        db.session.commit()

        return jsonify({
            'message': 'Inventory received successfully',
            'product_id': inventory_item.id,
            'product_name': inventory_item.name,
            'code': code,
            'quantity_added': quantity_to_add,
            'old_quantity': old_quantity,
            'new_quantity': inventory_item.quantity,
            'item': inventory_item_detail_to_dict(inventory_item)
        }), 200

    except ValueError as e:
        return jsonify({'error': f'Invalid quantity value: {str(e)}'}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error receiving inventory by code: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error receiving inventory by code: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/check-stock', methods=['POST'])
@login_required
def check_inventory_stock(current_user=None):
    """Check if items have sufficient stock"""
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'error': 'No items provided'}), 400
        
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
                inventory_item = Inventory.query.filter_by(part_number=part_number).first()
            
            # If not found by part number, try by name
            if not inventory_item:
                inventory_item = Inventory.query.filter(
                    Inventory.name.ilike(f"%{product_name}%")
                ).first()
            
            # If still not found, try by description
            if not inventory_item:
                inventory_item = Inventory.query.filter(
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
        
        return jsonify({
            'insufficient_items': insufficient_items,
            'available_items': available_items
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking inventory stock: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/deduct-items', methods=['POST'])
@role_required(['admin', 'inventory_manager'])
def deduct_inventory_items(current_user=None):
    """Deduct items from inventory"""
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'error': 'No items provided'}), 400
        
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
                    inventory_item = Inventory.query.get(inventory_id)
                else:
                    # Find by part number first (most accurate)
                    inventory_item = None
                    if part_number:
                        inventory_item = Inventory.query.filter_by(part_number=part_number).first()
                    
                    # If not found by part number, try by name
                    if not inventory_item:
                        inventory_item = Inventory.query.filter(
                            Inventory.name.ilike(f"%{product_name}%")
                        ).first()
                    
                    # If still not found, try by description
                    if not inventory_item:
                        inventory_item = Inventory.query.filter(
                            Inventory.description.ilike(f"%{product_name}%")
                        ).first()
                    
                    # If still not found, try exact name match
                    if not inventory_item:
                        inventory_item = Inventory.query.filter_by(name=product_name).first()
                
                if inventory_item:
                    # Store previous quantity for transaction logging
                    previous_quantity = inventory_item.quantity
                    
                    # Deduct the quantity (allow negative stock)
                    inventory_item.quantity -= quantity
                    inventory_item.updated_at = datetime.utcnow()
                    
                    # Log the transaction
                    user_id = current_user.id if current_user else None
                    log_issue_out(
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
        db.session.commit()
        
        return jsonify({
            'deducted_items': deducted_items,
            'failed_items': failed_items,
            'message': f'Successfully deducted {len(deducted_items)} items'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deducting inventory items: {e}")
        return jsonify({'error': 'Internal server error'}), 500 

@inventory_bp.route('/inventory/restock', methods=['POST'])
@role_required(['admin', 'inventory_manager'])
def restock_inventory(current_user=None):
    """Restock inventory items by increasing quantity"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        if 'product_id' not in data or 'quantity' not in data:
            return jsonify({'error': 'Product ID and quantity are required'}), 400
        
        product_id = data.get('product_id')
        quantity_to_add = int(data.get('quantity', 0))
        notes = data.get('notes', '')
        
        # Validate quantity
        if quantity_to_add <= 0:
            return jsonify({'error': 'Quantity must be greater than 0'}), 400
        
        # Find the inventory item
        inventory_item = Inventory.query.get(product_id)
        if not inventory_item:
            return jsonify({'error': 'Product not found'}), 404
        
        # Store old quantity for logging
        old_quantity = inventory_item.quantity
        
        # Increase the quantity
        inventory_item.quantity += quantity_to_add
        
        # Update the updated_at timestamp
        inventory_item.updated_at = datetime.utcnow()
        
        # Log the restock transaction
        user_id = current_user.id if current_user else None
        log_received(
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
        db.session.commit()
        
        return jsonify({
            'message': 'Inventory restocked successfully',
            'product_id': product_id,
            'product_name': inventory_item.name,
            'quantity_added': quantity_to_add,
            'old_quantity': old_quantity,
            'new_quantity': inventory_item.quantity,
            'notes': notes,
            'item': inventory_item_detail_to_dict(inventory_item)
        }), 200
        
    except ValueError as e:
        return jsonify({'error': f'Invalid quantity value: {str(e)}'}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error during restock: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error during restock: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ===== INVENTORY TRANSACTION HISTORY =====

@inventory_bp.route('/inventory/transactions', methods=['GET'])
@login_required
def get_inventory_transactions_route(current_user=None):
    """Get inventory transaction history with optional filters"""
    try:
        # Get query parameters
        inventory_id = request.args.get('inventory_id', type=int)
        transaction_type = request.args.get('transaction_type')
        repair_order_id = request.args.get('repair_order_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Limit per_page to prevent excessive memory usage
        per_page = min(per_page, 200)
        
        # Parse date filters
        date_from_obj = None
        date_to_obj = None
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Invalid date_from format. Use YYYY-MM-DD'}), 400
        
        if date_to:
            try:
                # Add 1 day to include the entire day
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
            except ValueError:
                return jsonify({'error': 'Invalid date_to format. Use YYYY-MM-DD'}), 400
        
        # Validate transaction type
        valid_types = ['issue_out', 'received', 'adjustment']
        if transaction_type and transaction_type not in valid_types:
            return jsonify({'error': f'Invalid transaction_type. Valid types: {valid_types}'}), 400
        
        # Get transactions using utility function
        transactions, pagination_info = get_inventory_transactions(
            inventory_id=inventory_id,
            transaction_type=transaction_type,
            repair_order_id=repair_order_id,
            date_from=date_from_obj,
            date_to=date_to_obj,
            page=page,
            per_page=per_page
        )
        
        return jsonify({
            'transactions': transactions,
            'pagination': pagination_info
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching inventory transactions: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@inventory_bp.route('/inventory/transactions/<int:transaction_id>', methods=['GET'])
@login_required
def get_inventory_transaction_detail(transaction_id, current_user=None):
    """Get details of a specific inventory transaction"""
    try:
        transaction = InventoryTransaction.query.get(transaction_id)
        
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404
        
        return jsonify(transaction.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error fetching inventory transaction {transaction_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@inventory_bp.route('/inventory/<int:item_id>/transactions', methods=['GET'])
@login_required
def get_item_transactions(item_id, current_user=None):
    """Get transaction history for a specific inventory item"""
    try:
        # Verify item exists
        item = Inventory.query.get(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 200)
        
        # Get transactions for this item
        transactions, pagination_info = get_inventory_transactions(
            inventory_id=item_id,
            page=page,
            per_page=per_page
        )
        
        return jsonify({
            'item': {
                'id': item.id,
                'name': item.name,
                'part_number': item.part_number,
                'current_quantity': item.quantity
            },
            'transactions': transactions,
            'pagination': pagination_info
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching transactions for item {item_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@inventory_bp.route('/inventory/<int:item_id>/ledger', methods=['GET'])
@login_required
def get_item_ledger(item_id, current_user=None):
    """Return date-wise in/out ledger used to back each inventory card Excel file."""
    try:
        if not item_id or item_id <= 0:
            return jsonify({'error': 'Invalid item ID'}), 400

        item = Inventory.query.get(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404

        ledger = build_item_daily_ledger(item)
        return jsonify({
            'item': inventory_item_detail_to_dict(item),
            'daily_rows': ledger['daily_rows'],
            'transactions': ledger['transactions'],
            'movement_date': ledger['movement_date'],
        }), 200

    except Exception as e:
        logger.error(f"Error building ledger for item {item_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500
