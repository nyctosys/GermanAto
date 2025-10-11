#!/usr/bin/env python3
"""
Utility functions for handling inventory deduction in repair orders
"""

import logging
from sqlalchemy.exc import SQLAlchemyError
from models import db, Inventory

logger = logging.getLogger(__name__)

def deduct_inventory_quantity(inventory_id, quantity_to_deduct):
    """
    Deduct quantity from inventory item
    Returns True if successful, False otherwise
    """
    try:
        inventory_item = Inventory.query.get(inventory_id)
        
        if not inventory_item:
            logger.error(f"Inventory item with ID {inventory_id} not found")
            return False
        
        # Allow negative values for repair orders
        inventory_item.quantity -= quantity_to_deduct
        
        # Update the updated_at timestamp
        from datetime import datetime
        inventory_item.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Successfully deducted {quantity_to_deduct} units from {inventory_item.name}. New quantity: {inventory_item.quantity}")
        return True
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error deducting inventory: {e}")
        return False
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error deducting inventory: {e}")
        return False

def find_inventory_item_by_part_number(part_number):
    """
    Find inventory item by part number
    Returns the inventory item or None if not found
    """
    try:
        return Inventory.query.filter_by(part_number=part_number).first()
    except Exception as e:
        logger.error(f"Error finding inventory item by part number {part_number}: {e}")
        return None

def find_inventory_item_by_name(name):
    """
    Find inventory item by name (exact match)
    Returns the inventory item or None if not found
    """
    try:
        return Inventory.query.filter_by(name=name).first()
    except Exception as e:
        logger.error(f"Error finding inventory item by name {name}: {e}")
        return None

def process_repair_order_parts(parts_data):
    """Process parts for repair order creation, deducting from inventory"""
    errors = []
    try:
        for part_data in parts_data:
            description = part_data.get('description', '').strip()
            quantity = int(part_data.get('quantity', 0))
            inventory_id = part_data.get('inventory_id')
            part_number = part_data.get('part_number', '').strip()
            
            if description and quantity > 0:
                if inventory_id:
                    # Direct inventory ID provided
                    success = deduct_inventory_quantity(inventory_id, quantity)
                    if not success:
                        errors.append(f"Failed to deduct inventory for part: {description}")
                elif part_number:
                    # Try to find by part number
                    inventory_item = find_inventory_item_by_part_number(part_number)
                    if inventory_item:
                        success = deduct_inventory_quantity(inventory_item.id, quantity)
                        if not success:
                            errors.append(f"Failed to deduct inventory for {part_number}")
                    else:
                        errors.append(f"Inventory item not found for part number: {part_number}")
                else:
                    # Try to find by description
                    inventory_item = find_inventory_item_by_name(description)
                    if inventory_item:
                        success = deduct_inventory_quantity(inventory_item.id, quantity)
                        if not success:
                            errors.append(f"Failed to deduct inventory for {description}")
                    else:
                        # No matching inventory item found, but continue
                        pass
        
        if not errors:
            db.session.commit()
            return True, parts_data, []
        else:
            db.session.rollback()
            return False, [], errors
            
    except Exception as e:
        db.session.rollback()
        return False, [], [f"Unexpected error: {str(e)}"]

def calculate_inventory_changes(old_parts, new_parts):
    """
    Calculate inventory changes when editing a repair order
    Returns a tuple: (items_to_add, items_to_remove, items_to_modify)
    """
    # Convert to dictionaries for easier comparison
    old_parts_dict = {}
    new_parts_dict = {}
    
    for part in old_parts:
        key = part.get('inventory_id') or part.get('part_number') or part.get('description')
        if key:
            old_parts_dict[key] = part
    
    for part in new_parts:
        key = part.get('inventory_id') or part.get('part_number') or part.get('description')
        if key:
            new_parts_dict[key] = part
    
    items_to_add = []
    items_to_remove = []
    items_to_modify = []
    
    # Find items to add (in new but not in old)
    for key, new_part in new_parts_dict.items():
        if key not in old_parts_dict:
            items_to_add.append(new_part)
    
    # Find items to remove (in old but not in new)
    for key, old_part in old_parts_dict.items():
        if key not in new_parts_dict:
            items_to_remove.append(old_part)
    
    # Find items to modify (in both but with different quantities)
    for key in old_parts_dict:
        if key in new_parts_dict:
            old_part = old_parts_dict[key]
            new_part = new_parts_dict[key]
            
            old_quantity = int(old_part.get('quantity', 0))
            new_quantity = int(new_part.get('quantity', 0))
            
            if old_quantity != new_quantity:
                items_to_modify.append({
                    'old': old_part,
                    'new': new_part,
                    'quantity_change': new_quantity - old_quantity
                })
    
    return items_to_add, items_to_remove, items_to_modify

def handle_repair_order_edit_inventory(old_parts, new_parts):
    """
    Handle inventory changes when editing a repair order
    Returns a tuple: (success, errors)
    """
    errors = []
    
    try:
        items_to_add, items_to_remove, items_to_modify = calculate_inventory_changes(old_parts, new_parts)
        
        # Handle items to remove (restore inventory)
        for item in items_to_remove:
            inventory_id = item.get('inventory_id')
            quantity = int(item.get('quantity', 0))
            
            if inventory_id and quantity > 0:
                inventory_item = Inventory.query.get(inventory_id)
                if inventory_item:
                    inventory_item.quantity += quantity
                    logger.info(f"Restored {quantity} units to {inventory_item.name} (ID: {inventory_id})")
                else:
                    errors.append(f"Inventory item with ID {inventory_id} not found for restoration")
        
        # Handle items to modify (adjust inventory)
        for item in items_to_modify:
            inventory_id = item['new'].get('inventory_id')
            quantity_change = item['quantity_change']
            
            if inventory_id and quantity_change != 0:
                inventory_item = Inventory.query.get(inventory_id)
                if inventory_item:
                    inventory_item.quantity -= quantity_change  # Subtract because we're deducting
                    logger.info(f"Adjusted inventory for {inventory_item.name} by {quantity_change} units")
                else:
                    errors.append(f"Inventory item with ID {inventory_id} not found for modification")
        
        # Handle items to add (deduct inventory)
        success, processed_parts, add_errors = process_repair_order_parts(items_to_add)
        errors.extend(add_errors)
        
        if not errors:
            db.session.commit()
            return True, []
        else:
            db.session.rollback()
            return False, errors
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error handling repair order edit inventory: {e}")
        return False, [f"Unexpected error: {str(e)}"] 