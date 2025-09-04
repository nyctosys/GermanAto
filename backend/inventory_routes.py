from flask import Blueprint, request, jsonify
from models import db, Inventory
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

inventory_bp = Blueprint('inventory', __name__)

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
    
    try:
        price = float(data.get('price', 0))
        if price < 0:
            errors.append("Price cannot be negative")
    except (ValueError, TypeError):
        errors.append("Price must be a valid number")
    
    # Validate reorder fields
    try:
        reorder_level = int(data.get('reorder_level', 5))
        if reorder_level < 0:
            errors.append("Reorder level cannot be negative")
    except (ValueError, TypeError):
        errors.append("Reorder level must be a valid number")
    
    try:
        reorder_quantity = int(data.get('reorder_quantity', 10))
        if reorder_quantity <= 0:
            errors.append("Reorder quantity must be greater than 0")
    except (ValueError, TypeError):
        errors.append("Reorder quantity must be a valid number")
    
    return errors

@inventory_bp.route('/inventory', methods=['GET'])
def get_inventory():
    """Get all inventory items"""
    try:
        inventory_items = Inventory.query.all()
        items_data = []
        
        for item in inventory_items:
            items_data.append({
                'id': item.id,
                'part_number': item.part_number,
                'name': item.name,
                'category': item.category,
                'quantity': item.quantity,
                'price': float(item.price),
                'description': item.description,
                'location': item.location,
                'reorder_level': item.reorder_level,
                'reorder_quantity': item.reorder_quantity,
                'created_at': item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': item.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return jsonify(items_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching inventory: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/<int:item_id>', methods=['GET'])
def get_inventory_item(item_id):
    """Get specific inventory item by ID"""
    try:
        if not item_id or item_id <= 0:
            return jsonify({'error': 'Invalid item ID'}), 400
        
        item = Inventory.query.get(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        item_data = {
            'id': item.id,
            'part_number': item.part_number,
            'name': item.name,
            'category': item.category,
            'quantity': item.quantity,
            'price': float(item.price),
            'description': item.description,
            'location': item.location,
            'reorder_level': item.reorder_level,
            'reorder_quantity': item.reorder_quantity,
            'created_at': item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'updated_at': item.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return jsonify(item_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching inventory item {item_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory', methods=['POST'])
def create_inventory_item():
    """Create a new inventory item"""
    try:
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
        quantity = int(data.get('quantity', 0))
        price = float(data.get('price', 0))
        description = str(data.get('description', '')).strip() if data.get('description') else None
        location = str(data.get('location', '')).strip() if data.get('location') else None
        reorder_level = int(data.get('reorder_level', 5))
        reorder_quantity = int(data.get('reorder_quantity', 10))
        
        # Create inventory item
        try:
            inventory_item = Inventory(
                name=name,
                category=category,
                quantity=quantity,
                price=price,
                description=description,
                location=location,
                reorder_level=reorder_level,
                reorder_quantity=reorder_quantity
            )
            db.session.add(inventory_item)
            db.session.commit()
            
            logger.info(f"Inventory item created successfully: ID {inventory_item.id}")
            
            return jsonify({
                'message': 'Inventory item created successfully',
                'item': {
                    'id': inventory_item.id,
                    'name': inventory_item.name,
                    'category': inventory_item.category,
                    'quantity': inventory_item.quantity,
                    'price': float(inventory_item.price),
                    'description': inventory_item.description,
                    'location': inventory_item.location,
                    'reorder_level': inventory_item.reorder_level,
                    'reorder_quantity': inventory_item.reorder_quantity,
                    'created_at': inventory_item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': inventory_item.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            }), 201
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error creating inventory item: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error creating inventory item: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/<int:item_id>', methods=['PUT'])
def update_inventory_item(item_id):
    """Update an existing inventory item"""
    try:
        if not item_id or item_id <= 0:
            return jsonify({'error': 'Invalid item ID'}), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Find the inventory item first
        item = Inventory.query.get(item_id)
        if not item:
            return jsonify({'error': 'Inventory item not found'}), 404
        
        # Validate input data
        validation_errors = validate_inventory_data(data)
        if validation_errors:
            return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
        
        # Extract and clean data
        name = str(data.get('name')).strip()
        category = str(data.get('category')).strip()
        quantity = int(data.get('quantity', 0))
        price = float(data.get('price', 0))
        description = str(data.get('description', '')).strip() if data.get('description') else None
        location = str(data.get('location', '')).strip() if data.get('location') else None
        reorder_level = int(data.get('reorder_level', 5))
        reorder_quantity = int(data.get('reorder_quantity', 10))
        
        # Update inventory item
        try:
            item.name = name
            item.category = category
            item.quantity = quantity
            item.price = price
            item.description = description
            item.location = location
            item.reorder_level = reorder_level
            item.reorder_quantity = reorder_quantity
            
            db.session.commit()
            
            logger.info(f"Inventory item updated successfully: ID {item.id}")
            
            return jsonify({
                'message': 'Inventory item updated successfully',
                'item': {
                    'id': item.id,
                    'name': item.name,
                    'category': item.category,
                    'quantity': item.quantity,
                    'price': float(item.price),
                    'description': item.description,
                    'location': item.location,
                    'reorder_level': item.reorder_level,
                    'reorder_quantity': item.reorder_quantity,
                    'created_at': item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': item.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            }), 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error updating inventory item {item_id}: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error updating inventory item {item_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/<int:item_id>', methods=['DELETE'])
def delete_inventory_item(item_id):
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
def search_inventory():
    """Search inventory items"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        # Search in part_number, name, description, location, and category
        search_results = Inventory.query.filter(
            db.or_(
                Inventory.part_number.ilike(f'%{query}%'),
                Inventory.name.ilike(f'%{query}%'),
                Inventory.description.ilike(f'%{query}%'),
                Inventory.location.ilike(f'%{query}%'),
                Inventory.category.ilike(f'%{query}%')
            )
        ).all()
        
        items_data = []
        for item in search_results:
            items_data.append({
                'id': item.id,
                'part_number': item.part_number,
                'name': item.name,
                'category': item.category,
                'quantity': item.quantity,
                'price': float(item.price),
                'description': item.description,
                'location': item.location,
                'created_at': item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': item.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return jsonify({
            'query': query,
            'results': items_data,
            'count': len(items_data)
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching inventory: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/stats', methods=['GET'])
def get_inventory_stats():
    """Get inventory statistics"""
    try:
        total_items = Inventory.query.count()
        total_value = db.session.query(db.func.sum(Inventory.quantity * Inventory.price)).scalar() or 0
        low_stock_items = Inventory.query.filter(Inventory.quantity < 10).count()
        
        # Category breakdown
        category_stats = db.session.query(
            Inventory.category,
            db.func.count(Inventory.id).label('count'),
            db.func.sum(Inventory.quantity * Inventory.price).label('total_value')
        ).group_by(Inventory.category).all()
        
        category_data = []
        for stat in category_stats:
            category_data.append({
                'category': stat.category,
                'count': stat.count,
                'total_value': float(stat.total_value or 0)
            })
        
        return jsonify({
            'total_items': total_items,
            'total_value': float(total_value),
            'low_stock_items': low_stock_items,
            'categories': category_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting inventory stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@inventory_bp.route('/inventory/low-stock', methods=['GET'])
def get_low_stock_items():
    """Get inventory items that are below reorder level, separated by urgency"""
    try:
        # Get items where quantity is less than or equal to reorder_level
        low_stock_items = Inventory.query.filter(Inventory.quantity <= Inventory.reorder_level).all()
        
        urgent_items = []  # Negative values (urgent)
        low_stock_items_data = []  # Regular low stock items
        
        for item in low_stock_items:
            item_data = {
                'id': item.id,
                'part_number': item.part_number,
                'name': item.name,
                'category': item.category,
                'quantity': item.quantity,
                'price': float(item.price),
                'description': item.description,
                'location': item.location,
                'reorder_level': item.reorder_level,
                'reorder_quantity': item.reorder_quantity,
                'needed_quantity': item.reorder_quantity,
                'created_at': item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': item.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            
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

@inventory_bp.route('/inventory/check-stock', methods=['POST'])
def check_inventory_stock():
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
def deduct_inventory_items():
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
                    # Deduct the quantity (allow negative stock)
                    inventory_item.quantity -= quantity
                    inventory_item.updated_at = datetime.utcnow()
                    
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
def restock_inventory():
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
            'notes': notes
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