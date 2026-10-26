#!/usr/bin/env python3
"""
Utility functions for handling inventory deduction in repair orders.

Shop-stock lines use the stock ledger (reserve/issue/return).
Customer-supplied lines never touch stock.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models import Inventory
from app.stock import (
    StockError,
    issue_to_ro,
    reserve,
    return_from_ro,
)

logger = logging.getLogger(__name__)


def _is_customer_supplied(part) -> bool:
    ownership = ""
    if hasattr(part, "ownership_type"):
        ownership = (part.ownership_type or "").strip().lower()
    elif isinstance(part, dict):
        ownership = (part.get("ownership_type") or "").strip().lower()
    return ownership in ("customer_supplied", "customer", "customer-supplied")


def deduct_inventory_quantity(db: Session, inventory_id, quantity_to_deduct, repair_order_id=None):
    """
    Reserve then issue shop-stock for an RO line. No negative stock.
    Returns True if successful, False otherwise.
    """
    try:
        inventory_item = db.get(Inventory, inventory_id)
        if not inventory_item:
            logger.error(f"Inventory item with ID {inventory_id} not found")
            return False

        reserve(
            db,
            item=inventory_item,
            qty=quantity_to_deduct,
            repair_order_id=repair_order_id,
            notes=f"Part: {inventory_item.name}",
        )
        issue_to_ro(
            db,
            item=inventory_item,
            qty=quantity_to_deduct,
            repair_order_id=repair_order_id,
            notes=f"Part: {inventory_item.name}",
            from_reserve=True,
        )
        # Caller owns the commit (process_repair_order_parts / edit handlers).
        logger.info(
            f"Issued {quantity_to_deduct} units from {inventory_item.name}. "
            f"New quantity: {inventory_item.quantity}"
        )
        return True

    except StockError as e:
        logger.error(f"Stock error deducting inventory: {e}")
        return False
    except SQLAlchemyError as e:
        logger.error(f"Database error deducting inventory: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deducting inventory: {e}")
        return False


def find_inventory_item_by_part_number(db: Session, part_number):
    """
    Find inventory item by part number
    Returns the inventory item or None if not found
    """
    try:
        return db.query(Inventory).filter_by(part_number=part_number).first()
    except Exception as e:
        logger.error(f"Error finding inventory item by part number {part_number}: {e}")
        return None


def find_inventory_item_by_name(db: Session, name):
    """
    Find inventory item by name (exact match)
    Returns the inventory item or None if not found
    """
    try:
        return db.query(Inventory).filter_by(name=name).first()
    except Exception as e:
        logger.error(f"Error finding inventory item by name {name}: {e}")
        return None


def process_repair_order_parts(db: Session, parts_data, repair_order_id=None):
    """Process parts for repair order creation; shop-stock hits the ledger."""
    errors = []
    try:
        for part_data in parts_data:
            if _is_customer_supplied(part_data):
                # Labour-only / customer-supplied: record on RO, no stock impact.
                continue
            description = part_data.get('description', '').strip()
            quantity = int(part_data.get('quantity', 0))
            inventory_id = part_data.get('inventory_id')
            part_number = part_data.get('part_number', '').strip()

            if description and quantity > 0:
                if inventory_id:
                    success = deduct_inventory_quantity(db, inventory_id, quantity, repair_order_id)
                    if not success:
                        errors.append(f"Failed to deduct inventory for part: {description}")
                elif part_number:
                    inventory_item = find_inventory_item_by_part_number(db, part_number)
                    if inventory_item:
                        success = deduct_inventory_quantity(
                            db, inventory_item.id, quantity, repair_order_id
                        )
                        if not success:
                            errors.append(f"Failed to deduct inventory for {part_number}")
                    else:
                        errors.append(f"Inventory item not found for part number: {part_number}")
                else:
                    inventory_item = find_inventory_item_by_name(db, description)
                    if inventory_item:
                        success = deduct_inventory_quantity(
                            db, inventory_item.id, quantity, repair_order_id
                        )
                        if not success:
                            errors.append(f"Failed to deduct inventory for {description}")

        if not errors:
            db.commit()
            return True, parts_data, []
        db.rollback()
        return False, [], errors

    except Exception as e:
        db.rollback()
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


def _resolve_inventory_id(db: Session, part):
    """Resolve inventory row id from explicit id, part number, or description."""
    inventory_id = part.get('inventory_id')
    if inventory_id is not None and inventory_id != '':
        try:
            return int(float(inventory_id))
        except (ValueError, TypeError):
            pass

    part_number = (part.get('part_number') or '').strip()
    if part_number:
        inventory_item = find_inventory_item_by_part_number(db, part_number)
        if inventory_item:
            return inventory_item.id

    description = (part.get('description') or '').strip()
    if description:
        inventory_item = find_inventory_item_by_name(db, description)
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


def handle_repair_order_edit_inventory(db: Session, old_parts, new_parts, repair_order_id=None):
    """Handle inventory changes when editing a repair order. Returns (success, errors)."""
    errors = []

    try:
        # Filter customer-supplied out of stock math
        old_shop = [p for p in old_parts if not _is_customer_supplied(p)]
        new_shop = [p for p in new_parts if not _is_customer_supplied(p)]
        items_to_add, items_to_remove, items_to_modify = calculate_inventory_changes(
            old_shop, new_shop
        )

        for item in items_to_remove:
            inventory_id = _resolve_inventory_id(db, item)
            quantity = _parse_part_quantity(item)
            if inventory_id and quantity > 0:
                inventory_item = db.get(Inventory, inventory_id)
                if inventory_item:
                    try:
                        return_from_ro(
                            db,
                            item=inventory_item,
                            qty=quantity,
                            repair_order_id=repair_order_id,
                            notes=f"Part: {inventory_item.name} - Returned to stock",
                        )
                    except StockError as exc:
                        errors.append(str(exc))
                else:
                    errors.append(f"Inventory item with ID {inventory_id} not found for restoration")

        for item in items_to_modify:
            inventory_id = _resolve_inventory_id(db, item["new"]) or _resolve_inventory_id(
                db, item["old"]
            )
            quantity_change = item["quantity_change"]
            if not inventory_id or quantity_change == 0:
                continue

            if quantity_change > 0:
                success = deduct_inventory_quantity(
                    db, inventory_id, quantity_change, repair_order_id
                )
                if not success:
                    part_label = (
                        item["new"].get("part_number")
                        or item["new"].get("description")
                        or inventory_id
                    )
                    errors.append(f"Failed to deduct additional inventory for part: {part_label}")
                continue

            inventory_item = db.get(Inventory, inventory_id)
            if inventory_item:
                try:
                    return_from_ro(
                        db,
                        item=inventory_item,
                        qty=abs(quantity_change),
                        repair_order_id=repair_order_id,
                        notes=f"Part: {inventory_item.name} - qty reduced on RO",
                    )
                except StockError as exc:
                    errors.append(str(exc))
            else:
                errors.append(f"Inventory item with ID {inventory_id} not found for modification")

        if items_to_add:
            _ok, _parts, add_errors = process_repair_order_parts(
                db, items_to_add, repair_order_id
            )
            # process_repair_order_parts commits/rollbacks — avoid double-commit path
            errors.extend(add_errors)
            if add_errors:
                return False, errors
            # process already committed adds; continue for remaining consistency
            return (False, errors) if errors else (True, [])

        if not errors:
            db.commit()
            return True, []
        db.rollback()
        return False, errors

    except Exception as e:
        db.rollback()
        logger.error(f"Error handling repair order edit inventory: {e}")
        return False, [f"Unexpected error: {str(e)}"]


def restore_inventory_for_deleted_repair_order(db: Session, parts, repair_order_id=None):
    """Restore inventory when a repair order is deleted. Returns (success, errors)."""
    errors = []

    try:
        for part in parts:
            if _is_customer_supplied(part):
                continue
            inventory_id = (
                part.inventory_id if hasattr(part, "inventory_id") else part.get("inventory_id")
            )
            quantity = (
                part.quantity
                if hasattr(part, "quantity")
                else int(part.get("quantity", 0))
            )

            if inventory_id and quantity > 0:
                inventory_item = db.get(Inventory, inventory_id)
                if inventory_item:
                    try:
                        return_from_ro(
                            db,
                            item=inventory_item,
                            qty=quantity,
                            repair_order_id=repair_order_id,
                            notes=f"Part: {inventory_item.name}",
                        )
                    except StockError as exc:
                        errors.append(str(exc))
                else:
                    errors.append(f"Inventory item with ID {inventory_id} not found")

        return True, errors

    except Exception as e:
        logger.error(f"Error restoring inventory for deleted repair order: {e}")
        return False, [f"Unexpected error: {str(e)}"]
