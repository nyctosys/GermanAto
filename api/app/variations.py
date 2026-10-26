"""Variation extras on an open RO → supplementary quote for line approval."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.document_links import apply_links
from app.foundation.audit import audit_write
from app.invoice_math import calculate_invoice_status, calculate_totals
from app.models import Invoice, InvoiceItem, InvoiceLabour, RepairOrder, Variation, VariationLine
from app.pipeline import assert_variation_line_billable


def create_variation(db: Session, ro: RepairOrder, data: dict, user) -> Variation:
    if ro.current_status in ("delivered", "cancelled"):
        raise HTTPException(status_code=400, detail="Cannot add variation on closed RO")
    var = Variation(
        repair_order_id=ro.id,
        status="draft",
        flagged_by=getattr(user, "username", None),
        notes=data.get("notes"),
        branch_id=ro.branch_id,
    )
    db.add(var)
    db.flush()
    for raw in data.get("lines") or []:
        line_type = (raw.get("line_type") or "labour").lower()
        qty = int(raw.get("quantity") or 1)
        price = float(raw.get("unit_price") or 0)
        if qty < 0 or price < 0:
            raise HTTPException(status_code=400, detail="quantity/price cannot be negative")
        db.add(
            VariationLine(
                variation_id=var.id,
                line_type=line_type,
                description=str(raw.get("description") or "").strip(),
                labour_code_id=raw.get("labour_code_id"),
                inventory_id=raw.get("inventory_id"),
                quantity=qty,
                unit_price=price,
                approval_status="pending",
                branch_id=ro.branch_id,
            )
        )
    db.flush()
    audit_write(
        db,
        user=user,
        action="CREATE",
        module="variations",
        reference_id=var.id,
        details=f"Variation on RO #{ro.id}",
        new_value=var.to_dict(),
    )
    return var


def send_variation_quote(db: Session, var: Variation, ro: RepairOrder, user) -> Invoice:
    items_data = []
    labours_data = []
    for ln in var.lines or []:
        if ln.line_type == "part":
            items_data.append(
                {
                    "product_name": ln.description,
                    "quantity": ln.quantity,
                    "price": ln.unit_price,
                    "proposed_price": ln.unit_price,
                    "inventory_id": ln.inventory_id,
                }
            )
        else:
            labours_data.append(
                {
                    "description": ln.description,
                    "price": ln.unit_price,
                    "proposed_price": ln.unit_price,
                    "labour_code_id": ln.labour_code_id,
                }
            )
    total = calculate_totals(items_data, labours_data)
    invoice = Invoice(
        customer_name=ro.customer_name,
        customer_address=ro.customer_address or "",
        customer_phone=ro.customer_phone or "",
        customer_reg_no=ro.customer_reg_no or "",
        customer_made=ro.customer_made or "",
        customer_mileage=ro.customer_mileage or "",
        customer_vin=ro.customer_vin,
        customer_color=ro.customer_color,
        customer_chasis=ro.customer_chasis,
        balance=total,
        advance=0,
        net_total=total,
        discount=0,
        type_of="quote",
        include_tax=False,
        tax_amount=0,
        status="pending",
        created_by_user=getattr(user, "username", None),
        customer_id=ro.customer_id,
        car_id=ro.car_id,
        visit_id=ro.visit_id,
        job_card_id=ro.job_card_id,
        repair_order_id=ro.id,
        is_variation=True,
        parent_quote_id=ro.quote_invoice_id,
    )
    apply_links(
        db,
        invoice,
        {"customer_id": ro.customer_id, "car_id": ro.car_id},
    )
    db.add(invoice)
    db.flush()
    for item in items_data:
        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                product_name=item["product_name"],
                quantity=item["quantity"],
                price=item["price"],
                proposed_price=item["proposed_price"],
                inventory_id=item.get("inventory_id"),
                approval_status="pending",
            )
        )
    for labour in labours_data:
        db.add(
            InvoiceLabour(
                invoice_id=invoice.id,
                description=labour["description"],
                price=labour["price"],
                proposed_price=labour["proposed_price"],
                labour_code_id=labour.get("labour_code_id"),
                approval_status="pending",
            )
        )
    invoice.status = calculate_invoice_status(invoice)
    var.quote_invoice_id = invoice.id
    var.status = "sent"
    db.flush()
    return invoice


def assert_line_workable(db: Session, *, from_variation_id: int | None, approval_status: str) -> None:
    assert_variation_line_billable(
        db, variation_id=from_variation_id, approval_status=approval_status
    )
