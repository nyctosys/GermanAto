#!/usr/bin/env python3
"""
Utility functions for inventory management
"""

from models import db, Inventory
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

def find_inventory_item_by_name(description):
    """
    Find inventory item by description/name
    Returns the inventory item if found, None otherwise
    """
    try:
        # Try to find exact match first
        inventory_item = Inventory.query.filter(
            Inventory.name.ilike(f"%{description}%")
        ).first()
        
        if inventory_item:
            return inventory_item
        
        # If no exact match, try partial match
        inventory_item = Inventory.query.filter(
            Inventory.description.ilike(f"%{description}%")
        ).first()
        
        return inventory_item
        
    except Exception as e:
        logger.error(f"Error finding inventory item by name '{description}': {e}")
        return None

# Inventory deduction functionality has been removed
def deduct_inventory_quantity(inventory_id, quantity_to_deduct):
    """
    Inventory deduction has been disabled - this function does nothing
    Returns True for compatibility
    """
    logger.info(f"Inventory deduction is disabled - no deduction performed for inventory ID {inventory_id}")
    return True

def add_inventory_quantity(inventory_id, quantity_to_add):
    """
    Add quantity to inventory item (for returns or corrections)
    Returns True if successful, False otherwise
    """
    try:
        inventory_item = Inventory.query.get(inventory_id)
        
        if not inventory_item:
            logger.error(f"Inventory item with ID {inventory_id} not found")
            return False
        
        # Add the quantity
        inventory_item.quantity += quantity_to_add
        
        # Update the updated_at timestamp
        from datetime import datetime
        inventory_item.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Successfully added {quantity_to_add} units to {inventory_item.name}. New quantity: {inventory_item.quantity}")
        return True
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error adding inventory: {e}")
        return False
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error adding inventory: {e}")
        return False

def process_repair_order_parts(parts_data):
    """Process parts for repair order - directly add without inventory deduction"""
    try:
        for part_data in parts_data:
            description = part_data.get('description', '').strip()
            quantity = int(part_data.get('quantity', 0))
            inventory_id = part_data.get('inventory_id')
            part_number = part_data.get('part_number', '').strip()
            
            if description and quantity > 0:
                # Add part directly without inventory deduction
                pass
                
    except Exception as e:
        return False, [], [f"Error processing parts: {str(e)}"]
    
    return True, parts_data, [] 