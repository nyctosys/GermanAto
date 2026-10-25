"""Utility functions for inventory management."""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Inventory

logger = logging.getLogger(__name__)


def find_inventory_item_by_name(db: Session, description):
    try:
        inventory_item = (
            db.query(Inventory).filter(Inventory.name.ilike(f"%{description}%")).first()
        )
        if inventory_item:
            return inventory_item
        return (
            db.query(Inventory)
            .filter(Inventory.description.ilike(f"%{description}%"))
            .first()
        )
    except Exception as e:
        logger.error(f"Error finding inventory item by name '{description}': {e}")
        return None


def deduct_inventory_quantity(inventory_id, quantity_to_deduct):
    """Inventory deduction has been disabled — returns True for compatibility."""
    logger.info(
        f"Inventory deduction is disabled - no deduction performed for inventory ID {inventory_id}"
    )
    return True


def add_inventory_quantity(db: Session, inventory_id, quantity_to_add):
    try:
        inventory_item = db.get(Inventory, inventory_id)
        if not inventory_item:
            logger.error(f"Inventory item with ID {inventory_id} not found")
            return False

        inventory_item.quantity += quantity_to_add
        inventory_item.updated_at = datetime.utcnow()
        db.commit()
        logger.info(
            f"Successfully added {quantity_to_add} units to {inventory_item.name}. "
            f"New quantity: {inventory_item.quantity}"
        )
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error adding inventory: {e}")
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error adding inventory: {e}")
        return False


def process_repair_order_parts(parts_data):
    """Process parts for repair order — directly add without inventory deduction."""
    try:
        for part_data in parts_data:
            description = part_data.get("description", "").strip()
            quantity = int(part_data.get("quantity", 0))
            if description and quantity > 0:
                pass
    except Exception as e:
        return False, [], [f"Error processing parts: {str(e)}"]
    return True, parts_data, []
