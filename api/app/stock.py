"""Stock movement ledger: on_hand / reserved / available + avg-cost on GRN.

Movement types:
  po_receive, reserve, release, issue_to_ro, return_from_ro, adjustment

Rules:
  - available = on_hand - reserved
  - no negative on_hand or reserved
  - avg_cost updates ONLY on po_receive
  - adjustments require reason + evidence + adjust_stock (caller enforces)
  - customer_supplied parts never call these helpers
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Inventory, InventoryTransaction, PurchaseOrder, VendorLedger

MOVEMENT_TYPES = frozenset(
    {
        "po_receive",
        "reserve",
        "release",
        "issue_to_ro",
        "return_from_ro",
        "adjustment",
        # legacy aliases still written by older helpers
        "issue_out",
        "received",
    }
)

PO_STATUSES = ("draft", "ordered", "partial", "received", "closed")


class StockError(ValueError):
    """Raised when a stock operation would violate balances."""


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def available(item: Inventory) -> int:
    on_hand = int(item.quantity or 0)
    reserved = int(getattr(item, "reserved", 0) or 0)
    return on_hand - reserved


def compute_avg_cost(
    on_hand: int,
    avg_cost: Decimal | float | str,
    recv_qty: int,
    unit_cost: Decimal | float | str,
) -> Decimal:
    """Weighted average after a GRN. Empty stock → new unit cost."""
    old_avg = _money(avg_cost)
    new_cost = _money(unit_cost)
    if recv_qty <= 0:
        return old_avg
    if on_hand <= 0:
        return new_cost
    total = (old_avg * on_hand) + (new_cost * recv_qty)
    return (total / (on_hand + recv_qty)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _snapshot(item: Inventory) -> tuple[int, int]:
    return int(item.quantity or 0), int(getattr(item, "reserved", 0) or 0)


def _log_movement(
    db: Session,
    *,
    item: Inventory,
    movement_type: str,
    quantity: int,
    on_hand_before: int,
    on_hand_after: int,
    reserved_before: int,
    reserved_after: int,
    unit_cost: Decimal | None = None,
    repair_order_id: int | None = None,
    purchase_order_id: int | None = None,
    reference_description: str | None = None,
    created_by: int | None = None,
    notes: str | None = None,
    reason: str | None = None,
    evidence_path: str | None = None,
) -> InventoryTransaction:
    if movement_type not in MOVEMENT_TYPES:
        raise StockError(f"unknown movement type: {movement_type}")
    txn = InventoryTransaction(
        inventory_id=item.id,
        transaction_type=movement_type,
        quantity=quantity,
        previous_quantity=on_hand_before,
        new_quantity=on_hand_after,
        reserved_before=reserved_before,
        reserved_after=reserved_after,
        unit_cost=unit_cost,
        repair_order_id=repair_order_id,
        purchase_order_id=purchase_order_id,
        reference_description=reference_description,
        created_by=created_by,
        notes=notes,
        reason=reason,
        evidence_path=evidence_path,
        created_at=datetime.utcnow(),
    )
    db.add(txn)
    return txn


def _touch(item: Inventory) -> None:
    item.updated_at = datetime.utcnow()


def po_receive(
    db: Session,
    *,
    item: Inventory,
    qty: int,
    unit_cost: Decimal | float | str,
    purchase_order: PurchaseOrder | None = None,
    created_by: int | None = None,
    notes: str | None = None,
    evidence_path: str | None = None,
) -> InventoryTransaction:
    """Increase on_hand and recompute avg_cost. Does not create vendor payable."""
    if qty <= 0:
        raise StockError("receive quantity must be positive")
    cost = _money(unit_cost)
    if cost < 0:
        raise StockError("unit cost cannot be negative")

    on_hand, reserved = _snapshot(item)
    new_avg = compute_avg_cost(on_hand, getattr(item, "avg_cost", 0) or 0, qty, cost)
    on_hand_after = on_hand + qty

    item.quantity = on_hand_after
    item.avg_cost = new_avg
    # Keep sell price untouched; cost is avg_cost only
    if getattr(item, "pending_purchase", False):
        item.pending_purchase = False
    _touch(item)

    return _log_movement(
        db,
        item=item,
        movement_type="po_receive",
        quantity=qty,
        on_hand_before=on_hand,
        on_hand_after=on_hand_after,
        reserved_before=reserved,
        reserved_after=reserved,
        unit_cost=cost,
        purchase_order_id=purchase_order.id if purchase_order else None,
        reference_description=(
            f"PO #{purchase_order.id} GRN {qty} @ {cost}"
            if purchase_order
            else f"GRN {qty} @ {cost}"
        ),
        created_by=created_by,
        notes=notes,
        evidence_path=evidence_path,
    )


def reserve(
    db: Session,
    *,
    item: Inventory,
    qty: int,
    repair_order_id: int | None = None,
    created_by: int | None = None,
    notes: str | None = None,
) -> InventoryTransaction:
    if qty <= 0:
        raise StockError("reserve quantity must be positive")
    on_hand, reserved = _snapshot(item)
    if available(item) < qty:
        raise StockError(
            f"insufficient available stock for {item.part_number or item.name}: "
            f"need {qty}, available {available(item)}"
        )
    reserved_after = reserved + qty
    item.reserved = reserved_after
    _touch(item)
    return _log_movement(
        db,
        item=item,
        movement_type="reserve",
        quantity=qty,
        on_hand_before=on_hand,
        on_hand_after=on_hand,
        reserved_before=reserved,
        reserved_after=reserved_after,
        repair_order_id=repair_order_id,
        reference_description=f"Reserved for RO #{repair_order_id}" if repair_order_id else "Reserved",
        created_by=created_by,
        notes=notes,
    )


def release(
    db: Session,
    *,
    item: Inventory,
    qty: int,
    repair_order_id: int | None = None,
    created_by: int | None = None,
    notes: str | None = None,
) -> InventoryTransaction:
    if qty <= 0:
        raise StockError("release quantity must be positive")
    on_hand, reserved = _snapshot(item)
    if reserved < qty:
        raise StockError(
            f"cannot release {qty}: only {reserved} reserved for {item.part_number or item.name}"
        )
    reserved_after = reserved - qty
    item.reserved = reserved_after
    _touch(item)
    return _log_movement(
        db,
        item=item,
        movement_type="release",
        quantity=qty,
        on_hand_before=on_hand,
        on_hand_after=on_hand,
        reserved_before=reserved,
        reserved_after=reserved_after,
        repair_order_id=repair_order_id,
        reference_description=f"Released for RO #{repair_order_id}" if repair_order_id else "Released",
        created_by=created_by,
        notes=notes,
    )


def issue_to_ro(
    db: Session,
    *,
    item: Inventory,
    qty: int,
    repair_order_id: int | None = None,
    created_by: int | None = None,
    notes: str | None = None,
    from_reserve: bool = True,
) -> InventoryTransaction:
    """Deduct on_hand; by default consume reserved qty first."""
    if qty <= 0:
        raise StockError("issue quantity must be positive")
    on_hand, reserved = _snapshot(item)

    if from_reserve:
        if reserved < qty:
            raise StockError(
                f"cannot issue {qty}: only {reserved} reserved for {item.part_number or item.name}"
            )
        if on_hand < qty:
            raise StockError(
                f"cannot issue {qty}: on_hand {on_hand} for {item.part_number or item.name}"
            )
        reserved_after = reserved - qty
    else:
        if available(item) < qty:
            raise StockError(
                f"insufficient available stock to issue {qty} of {item.part_number or item.name}"
            )
        reserved_after = reserved

    on_hand_after = on_hand - qty
    if on_hand_after < 0 or reserved_after < 0:
        raise StockError("negative stock prevented")

    item.quantity = on_hand_after
    item.reserved = reserved_after
    _touch(item)
    return _log_movement(
        db,
        item=item,
        movement_type="issue_to_ro",
        quantity=-qty,
        on_hand_before=on_hand,
        on_hand_after=on_hand_after,
        reserved_before=reserved,
        reserved_after=reserved_after,
        repair_order_id=repair_order_id,
        reference_description=f"Issued to RO #{repair_order_id}" if repair_order_id else "Issued",
        created_by=created_by,
        notes=notes,
    )


def return_from_ro(
    db: Session,
    *,
    item: Inventory,
    qty: int,
    repair_order_id: int | None = None,
    created_by: int | None = None,
    notes: str | None = None,
) -> InventoryTransaction:
    if qty <= 0:
        raise StockError("return quantity must be positive")
    on_hand, reserved = _snapshot(item)
    on_hand_after = on_hand + qty
    item.quantity = on_hand_after
    _touch(item)
    return _log_movement(
        db,
        item=item,
        movement_type="return_from_ro",
        quantity=qty,
        on_hand_before=on_hand,
        on_hand_after=on_hand_after,
        reserved_before=reserved,
        reserved_after=reserved,
        repair_order_id=repair_order_id,
        reference_description=(
            f"Returned from RO #{repair_order_id}" if repair_order_id else "Returned to stock"
        ),
        created_by=created_by,
        notes=notes,
    )


def adjust(
    db: Session,
    *,
    item: Inventory,
    delta: int,
    reason: str,
    evidence_path: str | None = None,
    created_by: int | None = None,
    notes: str | None = None,
) -> InventoryTransaction:
    if not (reason or "").strip():
        raise StockError("reason is required for stock adjustment")
    if not evidence_path:
        raise StockError("evidence attachment is required for stock adjustment")
    if delta == 0:
        raise StockError("adjustment delta cannot be zero")

    on_hand, reserved = _snapshot(item)
    on_hand_after = on_hand + delta
    if on_hand_after < 0:
        raise StockError("adjustment would make on_hand negative")
    if on_hand_after < reserved:
        raise StockError("adjustment would leave on_hand below reserved")

    item.quantity = on_hand_after
    _touch(item)
    return _log_movement(
        db,
        item=item,
        movement_type="adjustment",
        quantity=delta,
        on_hand_before=on_hand,
        on_hand_after=on_hand_after,
        reserved_before=reserved,
        reserved_after=reserved,
        reference_description=f"Adjustment: {reason}",
        created_by=created_by,
        notes=notes,
        reason=reason,
        evidence_path=evidence_path,
    )


def create_vendor_payable_for_grn(
    db: Session,
    *,
    purchase_order: PurchaseOrder,
    qty: int,
    unit_cost: Decimal | float | str,
    username: str | None = None,
    attachment_path: str | None = None,
) -> VendorLedger:
    """Debit vendor ledger (we owe supplier) for received goods."""
    cost = _money(unit_cost)
    amount = _money(cost * qty)
    last_entry = (
        db.query(VendorLedger)
        .filter_by(vendor_id=purchase_order.vendor_id)
        .order_by(VendorLedger.date.desc(), VendorLedger.id.desc())
        .first()
    )
    last_balance = _money(last_entry.balance) if last_entry else Decimal("0.00")
    new_balance = last_balance + amount  # debit increases payable
    entry = VendorLedger(
        vendor_id=purchase_order.vendor_id,
        date=date.today(),
        description=f"PO #{purchase_order.id} GRN {purchase_order.invoice_no}: "
        f"{purchase_order.item_name} x{qty}",
        folio=purchase_order.invoice_no,
        debit=amount,
        credit=Decimal("0.00"),
        balance=new_balance,
        created_by_user=username,
        attachment_path=attachment_path,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    return entry


def refresh_po_status(po: PurchaseOrder) -> str:
    """Set status from qty_received vs quantity. Does not force closed."""
    ordered = int(po.quantity or 0)
    received = int(getattr(po, "qty_received", 0) or 0)
    current = (po.status or "").strip().lower()
    if current in ("draft", "closed"):
        return current
    if received <= 0:
        po.status = "ordered"
    elif received < ordered:
        po.status = "partial"
    else:
        po.status = "received"
    return po.status


def stock_http(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail={"error": str(exc)})
