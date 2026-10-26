"""Purchase order goods receiving → inventory stock + vendor payable."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.foundation.audit import audit_write
from app.inventory_transaction_utils import log_received
from app.models import Inventory, PurchaseOrder, VendorLedger


def receive_po(
    db: Session,
    po: PurchaseOrder,
    *,
    qty: int,
    inventory_id: int | None,
    user,
) -> PurchaseOrder:
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Receive quantity must be > 0")
    ordered = int(po.quantity or 0)
    already = int(po.qty_received or 0)
    remaining = ordered - already
    if remaining <= 0:
        raise HTTPException(status_code=400, detail="Purchase order already fully received")
    if qty > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot receive {qty}; only {remaining} remaining on PO",
        )

    inv_id = inventory_id or po.inventory_id
    if not inv_id:
        # Match by item name
        inv = (
            db.query(Inventory)
            .filter(Inventory.name == po.item_name, Inventory.deleted_at.is_(None))
            .first()
        )
        if not inv:
            raise HTTPException(
                status_code=400,
                detail="inventory_id required (no matching inventory item for PO name)",
            )
        inv_id = inv.id
    else:
        inv = db.get(Inventory, inv_id)
        if not inv or inv.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Inventory item not found")

    prev = int(inv.quantity or 0)
    inv.quantity = prev + qty
    po.inventory_id = inv_id
    po.qty_received = already + qty
    if po.qty_received >= ordered:
        po.status = "received"
    else:
        po.status = "partial"

    log_received(
        db,
        inventory_id=inv.id,
        quantity=qty,
        previous_quantity=prev,
        new_quantity=inv.quantity,
        reference_description=f"PO #{po.id} receive ({po.invoice_no})",
        created_by=getattr(user, "id", None),
        notes=po.item_name,
    )

    # Vendor payable: debit increases what we owe for the received portion
    rate = Decimal(str(po.rate or 0))
    debit = (rate * Decimal(qty)).quantize(Decimal("0.01"))
    last = (
        db.query(VendorLedger)
        .filter(VendorLedger.vendor_id == po.vendor_id)
        .order_by(VendorLedger.id.desc())
        .first()
    )
    bal = Decimal(str(last.balance)) if last else Decimal("0")
    new_bal = bal + debit
    db.add(
        VendorLedger(
            vendor_id=po.vendor_id,
            date=date.today(),
            description=f"GRN PO #{po.id} — {po.item_name} x{qty}",
            folio=po.invoice_no,
            debit=debit,
            credit=Decimal("0"),
            balance=new_bal,
            created_by_user=getattr(user, "username", None),
        )
    )

    audit_write(
        db,
        user=user,
        action="RECEIVE",
        module="purchase_orders",
        reference_id=po.id,
        details=f"Received {qty} of {ordered} for {po.item_name}",
        new_value=po.to_dict(),
    )
    return po


def shortage_lines(db: Session, quote_invoice_id: int) -> list[dict]:
    """Approved quote parts where available stock < needed qty."""
    from app.models import Invoice

    quote = db.get(Invoice, quote_invoice_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    lines = []
    for item in quote.items or []:
        if (item.approval_status or "").lower() not in ("approved", "pending"):
            continue
        if not item.inventory_id:
            continue
        inv = db.get(Inventory, item.inventory_id)
        if not inv:
            continue
        need = int(item.quantity or 0)
        avail = int(inv.qty_available)
        short = need - avail
        if short > 0:
            lines.append(
                {
                    "inventory_id": inv.id,
                    "item_name": inv.name,
                    "part_number": inv.part_number,
                    "needed": need,
                    "available": avail,
                    "shortage": short,
                    "rate": float(inv.price or 0),
                }
            )
    return lines
