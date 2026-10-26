#!/usr/bin/env python3
"""
Utility functions for logging inventory transactions
Tracks all inventory movements: Issue Out, Received, Adjustment
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import InventoryTransaction, Inventory

logger = logging.getLogger(__name__)


def log_inventory_transaction(
    db: Session,
    inventory_id,
    transaction_type,
    quantity,
    previous_quantity,
    new_quantity,
    repair_order_id=None,
    reference_description=None,
    created_by=None,
    notes=None
):
    """
    Generic function to log an inventory transaction
    
    Args:
        inventory_id: ID of the inventory item
        transaction_type: 'issue_out', 'received', or 'adjustment'
        quantity: The quantity change (positive for received, negative for issue out)
        previous_quantity: Stock level before the transaction
        new_quantity: Stock level after the transaction
        repair_order_id: Optional repair order ID if related to a repair order
        reference_description: Description of the transaction
        created_by: User ID who performed the transaction
        notes: Additional notes
    
    Returns:
        InventoryTransaction object if successful, None otherwise
    """
    try:
        transaction = InventoryTransaction(
            inventory_id=inventory_id,
            transaction_type=transaction_type,
            quantity=quantity,
            previous_quantity=previous_quantity,
            new_quantity=new_quantity,
            repair_order_id=repair_order_id,
            reference_description=reference_description,
            created_by=created_by,
            notes=notes,
            created_at=datetime.utcnow()
        )
        
        db.add(transaction)
        # Note: Don't commit here - let the caller handle the commit
        # This allows the transaction to be part of a larger database transaction
        
        logger.info(f"Logged inventory transaction: {transaction_type} for inventory {inventory_id}, quantity: {quantity}")
        return transaction
        
    except Exception as e:
        logger.error(f"Error logging inventory transaction: {e}")
        return None


def log_issue_out(
    db: Session,
    inventory_id,
    quantity,
    previous_quantity,
    new_quantity,
    repair_order_id=None,
    reference_description=None,
    created_by=None,
    notes=None
):
    """
    Log an inventory issue out (deduction) transaction
    
    Args:
        inventory_id: ID of the inventory item
        quantity: The quantity being issued out (should be positive, will be stored as negative)
        previous_quantity: Stock level before the deduction
        new_quantity: Stock level after the deduction
        repair_order_id: Optional repair order ID
        reference_description: Description of why items were issued out
        created_by: User ID
        notes: Additional notes
    
    Returns:
        InventoryTransaction object if successful, None otherwise
    """
    # Store quantity as negative for issue out
    quantity_to_store = -abs(quantity)
    
    if not reference_description:
        if repair_order_id:
            reference_description = f"Issued out for Repair Order #{repair_order_id}"
        else:
            reference_description = "Manual inventory deduction"
    
    return log_inventory_transaction(
        db,
        inventory_id=inventory_id,
        transaction_type='issue_out',
        quantity=quantity_to_store,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
        repair_order_id=repair_order_id,
        reference_description=reference_description,
        created_by=created_by,
        notes=notes
    )


def log_received(
    db: Session,
    inventory_id,
    quantity,
    previous_quantity,
    new_quantity,
    repair_order_id=None,
    reference_description=None,
    created_by=None,
    notes=None
):
    """
    Log an inventory received (addition) transaction
    
    Args:
        inventory_id: ID of the inventory item
        quantity: The quantity being received (positive)
        previous_quantity: Stock level before the addition
        new_quantity: Stock level after the addition
        repair_order_id: Optional repair order ID (e.g., if restored from deletion)
        reference_description: Description of why items were received
        created_by: User ID
        notes: Additional notes
    
    Returns:
        InventoryTransaction object if successful, None otherwise
    """
    # Store quantity as positive for received
    quantity_to_store = abs(quantity)
    
    if not reference_description:
        if repair_order_id:
            reference_description = f"Restored from Repair Order #{repair_order_id} deletion"
        else:
            reference_description = "Inventory restock"
    
    return log_inventory_transaction(
        db,
        inventory_id=inventory_id,
        transaction_type='received',
        quantity=quantity_to_store,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
        repair_order_id=repair_order_id,
        reference_description=reference_description,
        created_by=created_by,
        notes=notes
    )


def log_adjustment(
    db: Session,
    inventory_id,
    quantity_change,
    previous_quantity,
    new_quantity,
    repair_order_id=None,
    reference_description=None,
    created_by=None,
    notes=None
):
    """
    Log an inventory adjustment transaction
    
    Args:
        inventory_id: ID of the inventory item
        quantity_change: The net quantity change (can be positive or negative)
        previous_quantity: Stock level before the adjustment
        new_quantity: Stock level after the adjustment
        repair_order_id: Optional repair order ID if related to a repair order edit
        reference_description: Description of why the adjustment was made
        created_by: User ID
        notes: Additional notes
    
    Returns:
        InventoryTransaction object if successful, None otherwise
    """
    if not reference_description:
        if repair_order_id:
            reference_description = f"Adjustment from Repair Order #{repair_order_id} edit"
        else:
            reference_description = "Manual quantity adjustment"
    
    return log_inventory_transaction(
        db,
        inventory_id=inventory_id,
        transaction_type='adjustment',
        quantity=quantity_change,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
        repair_order_id=repair_order_id,
        reference_description=reference_description,
        created_by=created_by,
        notes=notes
    )


def get_inventory_transactions(
    db: Session,
    inventory_id=None,
    transaction_type=None,
    repair_order_id=None,
    date_from=None,
    date_to=None,
    page=1,
    per_page=50
):
    """
    Get inventory transactions with optional filters
    
    Args:
        inventory_id: Filter by specific inventory item
        transaction_type: Filter by transaction type ('issue_out', 'received', 'adjustment')
        repair_order_id: Filter by repair order ID
        date_from: Filter from this date (datetime object)
        date_to: Filter to this date (datetime object)
        page: Page number for pagination
        per_page: Number of items per page
    
    Returns:
        Tuple of (transactions list, pagination info dict)
    """
    try:
        query = db.query(InventoryTransaction)
        
        if inventory_id:
            query = query.filter(InventoryTransaction.inventory_id == inventory_id)
        
        if transaction_type:
            if isinstance(transaction_type, (list, tuple, set, frozenset)):
                query = query.filter(
                    InventoryTransaction.transaction_type.in_(list(transaction_type))
                )
            else:
                query = query.filter(InventoryTransaction.transaction_type == transaction_type)
        
        if repair_order_id:
            query = query.filter(InventoryTransaction.repair_order_id == repair_order_id)
        
        if date_from:
            query = query.filter(InventoryTransaction.created_at >= date_from)
        
        if date_to:
            query = query.filter(InventoryTransaction.created_at <= date_to)
        
        # Order by newest first
        query = query.order_by(InventoryTransaction.created_at.desc())
        
        # Apply pagination
        total = query.count()
        pages = max(1, (total + per_page - 1) // per_page) if per_page else 1
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        transactions = [t.to_dict() for t in items]
        pagination_info = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': pages,
            'has_next': page < pages,
            'has_prev': page > 1
        }
        
        return transactions, pagination_info
        
    except Exception as e:
        logger.error(f"Error getting inventory transactions: {e}")
        return [], {'page': 1, 'per_page': per_page, 'total': 0, 'pages': 0, 'has_next': False, 'has_prev': False}
