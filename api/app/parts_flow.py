"""Parts reserve on quote approval → issue on RO open → return unused on close."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.inventory_transaction_utils import log_inventory_transaction
from app.models import Inventory, Invoice, RepairOrder, RepairOrderPart


def _inv(db: Session, inventory_id: int) -> Inventory:
    row = db.get(Inventory, inventory_id)
    if not row or row.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Inventory {inventory_id} not found")
    return row


def reserve_for_quote(db: Session, quote: Invoice, *, created_by: int | None = None) -> list[str]:
    """Reserve customer-approved part lines."""
    warnings: list[str] = []
    for item in quote.items or []:
        if (item.approval_status or "").lower() != "approved":
            continue
        if not item.inventory_id:
            continue
        inv = _inv(db, item.inventory_id)
        qty = int(item.quantity or 0)
        if qty <= 0:
            continue
        available = int(inv.quantity or 0) - int(inv.reserved or 0)
        if qty > available:
            warnings.append(
                f"{inv.name}: reserve {qty} but only {available} available"
            )
            # Still reserve what we can? Spec says reserved on approval — fail hard.
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock to reserve {inv.name}: need {qty}, available {available}",
            )
        prev = inv.reserved or 0
        inv.reserved = prev + qty
        log_inventory_transaction(
            db,
            inventory_id=inv.id,
            transaction_type="reserve",
            quantity=qty,
            previous_quantity=inv.quantity,
            new_quantity=inv.quantity,
            reference_description=f"Reserved for quote #{quote.id}",
            created_by=created_by,
            notes=f"reserved {prev} → {inv.reserved}",
        )
    return warnings


def release_quote_reserves(db: Session, quote: Invoice, *, created_by: int | None = None) -> None:
    for item in quote.items or []:
        if (item.approval_status or "").lower() != "approved":
            continue
        if not item.inventory_id:
            continue
        inv = _inv(db, item.inventory_id)
        qty = int(item.quantity or 0)
        if qty <= 0:
            continue
        prev = inv.reserved or 0
        inv.reserved = max(0, prev - qty)
        log_inventory_transaction(
            db,
            inventory_id=inv.id,
            transaction_type="release",
            quantity=-qty,
            previous_quantity=inv.quantity,
            new_quantity=inv.quantity,
            reference_description=f"Released reserve for quote #{quote.id}",
            created_by=created_by,
        )


def issue_on_ro_open(
    db: Session,
    ro: RepairOrder,
    quote: Invoice | None,
    *,
    created_by: int | None = None,
) -> None:
    """Convert reserves into issued stock when RO opens; create RO parts from approved quote lines.

    Legacy quotes (all pending) still issue parts so existing data keeps working.
    """
    if quote is None:
        return
    statuses = [(i.approval_status or "pending").lower() for i in (quote.items or [])]
    statuses += [(l.approval_status or "pending").lower() for l in (quote.labours or [])]
    legacy = bool(statuses) and all(s == "pending" for s in statuses)

    for item in quote.items or []:
        st = (item.approval_status or "pending").lower()
        if st == "rejected":
            continue
        if st != "approved" and not legacy:
            continue
        if not item.inventory_id:
            continue
        inv = _inv(db, item.inventory_id)
        qty = int(item.quantity or 0)
        if qty <= 0:
            continue
        # Release reserve then issue out of on-hand
        prev_res = inv.reserved or 0
        inv.reserved = max(0, prev_res - qty)
        prev_qty = inv.quantity or 0
        inv.quantity = prev_qty - qty
        log_inventory_transaction(
            db,
            inventory_id=inv.id,
            transaction_type="issue_out",
            quantity=-qty,
            previous_quantity=prev_qty,
            new_quantity=inv.quantity,
            repair_order_id=ro.id,
            reference_description=f"Issued for RO #{ro.id} from quote #{quote.id}",
            created_by=created_by,
            notes=f"reserve {prev_res} → {inv.reserved}",
        )
        part = RepairOrderPart(
            repair_order_id=ro.id,
            inventory_id=inv.id,
            description=item.product_name,
            part_number=item.part_number or inv.part_number,
            quantity=qty,
            status="issued",
            qty_reserved=0,
            qty_issued=qty,
            qty_returned=0,
        )
        db.add(part)


def return_unused_on_close(
    db: Session,
    ro: RepairOrder,
    *,
    created_by: int | None = None,
) -> None:
    for part in ro.parts or []:
        issued = int(part.qty_issued or part.quantity or 0)
        returned = int(part.qty_returned or 0)
        unused = issued - returned
        if unused <= 0 or not part.inventory_id:
            continue
        inv = _inv(db, part.inventory_id)
        prev = inv.quantity or 0
        inv.quantity = prev + unused
        part.qty_returned = returned + unused
        part.status = "returned"
        log_inventory_transaction(
            db,
            inventory_id=inv.id,
            transaction_type="return",
            quantity=unused,
            previous_quantity=prev,
            new_quantity=inv.quantity,
            repair_order_id=ro.id,
            reference_description=f"Returned unused from RO #{ro.id}",
            created_by=created_by,
        )
