#!/usr/bin/env python3
"""
Utility functions for handling inventory deduction in repair orders
"""

import logging
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from models import db, Inventory
from inventory_transaction_utils import log_issue_out, log_received, log_adjustment

logger = logging.getLogger(__name__)


def deduct_inventory_quantity(inventory_id, quantity_to_deduct, repair_order_id=None):
    """
    Deduct quantity from inventory item
    Returns True if successful, False otherwise
    """
    try:
        inventory_item = Inventory.query.get(inventory_id)
        
        if not inventory_item:
            logger.error(f"Inventory item with ID {inventory_id} not found")
            return False
        
        # Store previous quantity for transaction logging
        previous_quantity = inventory_item.quantity
        
        # Allow negative values for repair orders
        inventory_item.quantity -= quantity_to_deduct
        
        # Update the updated_at timestamp
        inventory_item.updated_at = datetime.utcnow()
        
        # Log the transaction
        log_issue_out(
            inventory_id=inventory_id,
            quantity=quantity_to_deduct,
            previous_quantity=previous_quantity,
            new_quantity=inventory_item.quantity,
            repair_order_id=repair_order_id,
            reference_description=f"Issued for Repair Order #{repair_order_id}" if repair_order_id else "Repair order part deduction",
            notes=f"Part: {inventory_item.name}"
        )
        
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


def process_repair_order_parts(parts_data, repair_order_id=None):
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
                    success = deduct_inventory_quantity(inventory_id, quantity, repair_order_id)
                    if not success:
                        errors.append(f"Failed to deduct inventory for part: {description}")
                elif part_number:
                    # Try to find by part number
                    inventory_item = find_inventory_item_by_part_number(part_number)
                    if inventory_item:
                        success = deduct_inventory_quantity(inventory_item.id, quantity, repair_order_id)
                        if not success:
                            errors.append(f"Failed to deduct inventory for {part_number}")
                    else:
                        errors.append(f"Inventory item not found for part number: {part_number}")
                else:
                    # Try to find by description
                    inventory_item = find_inventory_item_by_name(description)
                    if inventory_item:
                        success = deduct_inventory_quantity(inventory_item.id, quantity, repair_order_id)
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


def _get_part_inventory_key(part):
    """Stable identity for matching repair-order part lines to inventory."""
    inv_id = part.get('inventory_id')
    if inv_id is not None and inv_id != '':
        try:
            # Cast string/float ids to int for reliable comparison (e.g., "9" vs 9)
            return int(float(inv_id))
        except (ValueError, TypeError):
            pass

    part_number = (part.get('part_number') or '').strip()
    if part_number:
        return f"pn:{part_number}"

    description = (part.get('description') or '').strip()
    if description:
        return f"desc:{description}"

    return None


def _parse_part_quantity(part):
    try:
        return int(part.get('quantity', 0) or 0)
    except (ValueError, TypeError):
        return 0


def _aggregate_parts_by_inventory_key(parts):
    """
    Sum quantities for duplicate line items that share the same inventory identity.

    Repair orders allow the same part number on multiple rows. Inventory must
    compare total quantity per part, not last-row-wins, or a second PN line
    produces no stock deduction and no sale transaction.
    """
    aggregated = {}

    for part in parts:
        key = _get_part_inventory_key(part)
        if not key:
            continue

        quantity = _parse_part_quantity(part)
        if key in aggregated:
            aggregated[key]['quantity'] = _parse_part_quantity(aggregated[key]) + quantity
            if not aggregated[key].get('inventory_id') and part.get('inventory_id'):
                aggregated[key]['inventory_id'] = part.get('inventory_id')
            if not (aggregated[key].get('part_number') or '').strip() and (part.get('part_number') or '').strip():
                aggregated[key]['part_number'] = part.get('part_number')
            if not (aggregated[key].get('description') or '').strip() and (part.get('description') or '').strip():
                aggregated[key]['description'] = part.get('description')
        else:
            aggregated[key] = dict(part)
            aggregated[key]['quantity'] = quantity

    return aggregated


def _resolve_inventory_id(part):
    """Resolve inventory row id from explicit id, part number, or description."""
    inventory_id = part.get('inventory_id')
    if inventory_id is not None and inventory_id != '':
        try:
            return int(float(inventory_id))
        except (ValueError, TypeError):
            pass

    part_number = (part.get('part_number') or '').strip()
    if part_number:
        inventory_item = find_inventory_item_by_part_number(part_number)
        if inventory_item:
            return inventory_item.id

    description = (part.get('description') or '').strip()
    if description:
        inventory_item = find_inventory_item_by_name(description)
        if inventory_item:
            return inventory_item.id

    return None


def calculate_inventory_changes(old_parts, new_parts):
    """
    Calculate inventory changes when editing a repair order.

    Duplicate lines for the same inventory item are aggregated by quantity so
    re-adding the same part number is treated as an additional sale.

    Returns a tuple: (items_to_add, items_to_remove, items_to_modify)
    """
    old_parts_dict = _aggregate_parts_by_inventory_key(old_parts)
    new_parts_dict = _aggregate_parts_by_inventory_key(new_parts)

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

    # Find items to modify (in both but with different total quantities)
    for key in old_parts_dict:
        if key in new_parts_dict:
            old_part = old_parts_dict[key]
            new_part = new_parts_dict[key]

            old_quantity = _parse_part_quantity(old_part)
            new_quantity = _parse_part_quantity(new_part)

            if old_quantity != new_quantity:
                items_to_modify.append({
                    'old': old_part,
                    'new': new_part,
                    'quantity_change': new_quantity - old_quantity
                })

    return items_to_add, items_to_remove, items_to_modify


def handle_repair_order_edit_inventory(old_parts, new_parts, repair_order_id=None):
    """
    Handle inventory changes when editing a repair order
    Returns a tuple: (success, errors)
    """
    errors = []

    try:
        items_to_add, items_to_remove, items_to_modify = calculate_inventory_changes(old_parts, new_parts)

        # Handle items to remove (restore inventory - parts removed from repair order)
        for item in items_to_remove:
            inventory_id = _resolve_inventory_id(item)
            quantity = _parse_part_quantity(item)

            if inventory_id and quantity > 0:
                inventory_item = Inventory.query.get(inventory_id)
                if inventory_item:
                    previous_quantity = inventory_item.quantity
                    inventory_item.quantity += quantity

                    # Log the adjustment (items returned to inventory)
                    log_adjustment(
                        inventory_id=inventory_id,
                        quantity_change=quantity,  # positive because we're adding back
                        previous_quantity=previous_quantity,
                        new_quantity=inventory_item.quantity,
                        repair_order_id=repair_order_id,
                        reference_description=f"Part removed from Repair Order #{repair_order_id}" if repair_order_id else "Part removed from repair order",
                        notes=f"Part: {inventory_item.name} - Returned to stock"
                    )

                    logger.info(f"Restored {quantity} units to {inventory_item.name} (ID: {inventory_id})")
                else:
                    errors.append(f"Inventory item with ID {inventory_id} not found for restoration")

        # Handle items to modify (quantity changed for an existing inventory identity)
        for item in items_to_modify:
            inventory_id = _resolve_inventory_id(item['new']) or _resolve_inventory_id(item['old'])
            quantity_change = item['quantity_change']

            if not inventory_id or quantity_change == 0:
                continue

            if quantity_change > 0:
                # Extra units issued for the RO — must be issue_out so it counts as a sale
                success = deduct_inventory_quantity(inventory_id, quantity_change, repair_order_id)
                if not success:
                    part_label = (
                        item['new'].get('part_number')
                        or item['new'].get('description')
                        or inventory_id
                    )
                    errors.append(f"Failed to deduct additional inventory for part: {part_label}")
                continue

            # quantity_change < 0: return units to stock
            quantity_to_restore = abs(quantity_change)
            inventory_item = Inventory.query.get(inventory_id)
            if inventory_item:
                previous_quantity = inventory_item.quantity
                inventory_item.quantity += quantity_to_restore

                log_adjustment(
                    inventory_id=inventory_id,
                    quantity_change=quantity_to_restore,
                    previous_quantity=previous_quantity,
                    new_quantity=inventory_item.quantity,
                    repair_order_id=repair_order_id,
                    reference_description=f"Part quantity reduced in Repair Order #{repair_order_id}" if repair_order_id else "Part quantity reduced in repair order",
                    notes=f"Part: {inventory_item.name} - Returned to stock: {quantity_to_restore}"
                )

                logger.info(
                    f"Restored {quantity_to_restore} units to {inventory_item.name} "
                    f"after quantity reduction on repair order"
                )
            else:
                errors.append(f"Inventory item with ID {inventory_id} not found for modification")

        # Handle items to add (deduct inventory - new parts added)
        if items_to_add:
            success, processed_parts, add_errors = process_repair_order_parts(items_to_add, repair_order_id)
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


def restore_inventory_for_deleted_repair_order(parts, repair_order_id=None):
    """
    Restore inventory when a repair order is deleted
    Returns a tuple: (success, errors)
    """
    errors = []
    
    try:
        for part in parts:
            inventory_id = part.inventory_id if hasattr(part, 'inventory_id') else part.get('inventory_id')
            quantity = part.quantity if hasattr(part, 'quantity') else int(part.get('quantity', 0))
            
            if inventory_id and quantity > 0:
                inventory_item = Inventory.query.get(inventory_id)
                if inventory_item:
                    previous_quantity = inventory_item.quantity
                    inventory_item.quantity += quantity
                    
                    # Log the transaction as received (inventory restored)
                    log_received(
                        inventory_id=inventory_id,
                        quantity=quantity,
                        previous_quantity=previous_quantity,
                        new_quantity=inventory_item.quantity,
                        repair_order_id=repair_order_id,
                        reference_description=f"Inventory restored from Repair Order #{repair_order_id} deletion" if repair_order_id else "Inventory restored from repair order deletion",
                        notes=f"Part: {inventory_item.name}"
                    )
                    
                    logger.info(f"Restored {quantity} units to {inventory_item.name} (ID: {inventory_id}) from deleted repair order")
                else:
                    errors.append(f"Inventory item with ID {inventory_id} not found")
        
        return True, errors
        
    except Exception as e:
        logger.error(f"Error restoring inventory for deleted repair order: {e}")
        return False, [f"Unexpected error: {str(e)}"]
