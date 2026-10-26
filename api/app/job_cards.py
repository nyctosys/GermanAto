"""Job card CRUD + pull lines into a quotation."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.foundation.audit import audit_write
from app.models import (
    Invoice,
    InvoiceItem,
    InvoiceLabour,
    JobCard,
    JobCardLine,
    LabourCode,
    Inventory,
)
from app.pipeline import assert_can_create_job_card, assert_quote_from_job_card, discount_pct
from app.foundation.overrides import assert_discount_override
from app.document_links import apply_links
from app.invoice_math import calculate_invoice_status, calculate_totals


LINE_STATUSES = {"Pending", "Approved", "Rejected", "In progress", "Done", "QC passed"}
PAY_TYPES = {"customer", "warranty", "internal"}


def create_job_card(db: Session, data: dict, user) -> JobCard:
    car_id = data.get("car_id")
    visit_id = data.get("visit_id")
    car_id_i = int(car_id) if car_id not in (None, "") else None
    visit_id_i = int(visit_id) if visit_id not in (None, "") else None
    assert_can_create_job_card(db, car_id=car_id_i, visit_id=visit_id_i)

    card = JobCard(
        visit_id=visit_id_i,
        car_id=car_id_i,
        customer_id=int(data["customer_id"]) if data.get("customer_id") else None,
        customer_name=str(data.get("customer_name") or "").strip(),
        customer_phone=str(data.get("customer_phone") or "").strip(),
        customer_reg_no=str(data.get("customer_reg_no") or "").strip(),
        customer_made=str(data.get("customer_made") or "").strip(),
        notes=data.get("notes"),
        status="open",
        created_by_user=getattr(user, "username", None),
    )
    db.add(card)
    db.flush()
    for raw in data.get("lines") or []:
        db.add(_build_line(db, card.id, raw))
    db.flush()
    audit_write(
        db,
        user=user,
        action="CREATE",
        module="job_cards",
        reference_id=card.id,
        details=f"Job card for {card.customer_name}",
        new_value=card.to_dict(),
    )
    return card


def _build_line(db: Session, job_card_id: int, raw: dict) -> JobCardLine:
    line_type = (raw.get("line_type") or "labour").lower()
    if line_type not in ("labour", "part"):
        raise HTTPException(status_code=400, detail="line_type must be labour or part")
    pay_type = (raw.get("pay_type") or "customer").lower()
    if pay_type not in PAY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid pay_type: {pay_type}")
    status = raw.get("line_status") or "Pending"
    if status not in LINE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid line_status: {status}")

    labour_code_id = raw.get("labour_code_id")
    inventory_id = raw.get("inventory_id")
    description = str(raw.get("description") or "").strip()
    unit_price = float(raw.get("unit_price") or 0)
    std_hours = raw.get("std_hours")
    qty = int(raw.get("quantity") or 1)
    if qty < 0 or unit_price < 0:
        raise HTTPException(status_code=400, detail="quantity/price cannot be negative")

    if line_type == "labour":
        if labour_code_id:
            code = db.get(LabourCode, int(labour_code_id))
            if not code or not code.is_active:
                raise HTTPException(status_code=400, detail="Labour code not found")
            description = description or code.description
            unit_price = unit_price or float(code.rate or 0)
            std_hours = std_hours if std_hours is not None else code.standard_hours
        elif not description:
            raise HTTPException(status_code=400, detail="Labour line needs code or description")
    else:
        if not inventory_id:
            raise HTTPException(status_code=400, detail="Part lines require inventory_id (picker)")
        inv = db.get(Inventory, int(inventory_id))
        if not inv or inv.deleted_at is not None:
            raise HTTPException(status_code=400, detail="Inventory part not found")
        description = description or inv.name
        unit_price = unit_price if "unit_price" in raw else float(inv.price or 0)

    return JobCardLine(
        job_card_id=job_card_id,
        line_type=line_type,
        labour_code_id=int(labour_code_id) if labour_code_id else None,
        inventory_id=int(inventory_id) if inventory_id else None,
        description=description,
        part_number=raw.get("part_number"),
        quantity=qty,
        std_hours=float(std_hours) if std_hours is not None else None,
        unit_price=unit_price,
        pay_type=pay_type,
        assigned_technician=raw.get("assigned_technician"),
        line_status=status,
    )


def replace_lines(db: Session, card: JobCard, lines: list[dict]) -> JobCard:
    card.lines.clear()
    db.flush()
    for raw in lines:
        db.add(_build_line(db, card.id, raw))
    db.flush()
    return card


def get_job_card(db: Session, job_card_id: int) -> JobCard:
    card = (
        db.query(JobCard)
        .options(joinedload(JobCard.lines))
        .filter(JobCard.id == job_card_id, JobCard.deleted_at.is_(None))
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Job card not found")
    return card


def build_quote_from_job_card(
    db: Session,
    card: JobCard,
    data: dict,
    user,
) -> Invoice:
    assert_quote_from_job_card(card)
    items_data = []
    labours_data = []
    for ln in card.lines or []:
        if ln.pay_type == "internal":
            continue
        if ln.line_type == "part":
            price = float(ln.unit_price or 0)
            items_data.append(
                {
                    "product_name": ln.description,
                    "part_number": ln.part_number,
                    "quantity": ln.quantity,
                    "price": price,
                    "proposed_price": price,
                    "inventory_id": ln.inventory_id,
                    "job_card_line_id": ln.id,
                }
            )
        else:
            price = float(ln.unit_price or 0)
            labours_data.append(
                {
                    "description": ln.description,
                    "price": price,
                    "proposed_price": price,
                    "labour_code_id": ln.labour_code_id,
                    "std_hours": ln.std_hours,
                    "job_card_line_id": ln.id,
                }
            )

    # Allow price edits from body overlay
    edited_items = data.get("items")
    edited_labours = data.get("labours")
    if edited_items is not None:
        items_data = edited_items
    if edited_labours is not None:
        labours_data = edited_labours

    total = calculate_totals(items_data, labours_data)
    discount = float(data.get("discount") or 0)
    advance = float(data.get("advance") or 0)
    include_tax = bool(data.get("include_tax", False))
    tax_amount = float(data.get("tax_amount") or 0)
    if include_tax:
        balance = round(total + tax_amount - discount - advance, 2)
    else:
        balance = round(total - discount - advance, 2)

    pct = discount_pct(discount, total)
    assert_discount_override(db, user, pct, reason=data.get("reason"))

    invoice = Invoice(
        customer_name=data.get("customer_name") or card.customer_name,
        customer_address=str(data.get("customer_address") or ""),
        customer_phone=data.get("customer_phone") or card.customer_phone,
        customer_reg_no=data.get("customer_reg_no") or card.customer_reg_no,
        customer_made=data.get("customer_made") or card.customer_made,
        customer_mileage=str(data.get("customer_mileage") or ""),
        customer_vin=data.get("customer_vin"),
        customer_color=data.get("customer_color"),
        customer_chasis=data.get("customer_chasis"),
        balance=balance,
        advance=advance,
        net_total=total,
        discount=discount,
        type_of="quote",
        include_tax=include_tax,
        tax_amount=tax_amount,
        status="pending",
        created_by_user=getattr(user, "username", None),
        visit_id=card.visit_id,
        job_card_id=card.id,
        customer_id=card.customer_id,
        car_id=card.car_id,
    )
    apply_links(db, invoice, {**data, "customer_id": card.customer_id, "car_id": card.car_id})
    db.add(invoice)
    db.flush()

    for item in items_data:
        proposed = float(item.get("proposed_price", item.get("price", 0)))
        price = float(item["price"])
        if abs(price - proposed) > 0.001 and not data.get("reason"):
            from app.foundation.overrides import require_audit_reason

            require_audit_reason(kind="price_edit", reason=data.get("reason"))
        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                product_name=str(item["product_name"]).strip(),
                part_number=item.get("part_number"),
                quantity=int(item["quantity"]),
                price=price,
                proposed_price=proposed,
                inventory_id=item.get("inventory_id"),
                job_card_line_id=item.get("job_card_line_id"),
                approval_status="pending",
            )
        )
    for labour in labours_data:
        proposed = float(labour.get("proposed_price", labour.get("price", 0)))
        price = float(labour["price"])
        if abs(price - proposed) > 0.001 and not data.get("reason"):
            from app.foundation.overrides import require_audit_reason

            require_audit_reason(kind="price_edit", reason=data.get("reason"))
        db.add(
            InvoiceLabour(
                invoice_id=invoice.id,
                description=str(labour["description"]).strip(),
                price=price,
                proposed_price=proposed,
                labour_code_id=labour.get("labour_code_id"),
                std_hours=labour.get("std_hours"),
                job_card_line_id=labour.get("job_card_line_id"),
                approval_status="pending",
            )
        )

    invoice.status = calculate_invoice_status(invoice)
    card.quote_invoice_id = invoice.id
    card.status = "quoted"
    db.flush()
    audit_write(
        db,
        user=user,
        action="CREATE_QUOTE",
        module="job_cards",
        reference_id=card.id,
        details=f"Quote #{invoice.id} from job card",
        new_value={"invoice_id": invoice.id, "net_total": invoice.net_total},
        reason=data.get("reason"),
    )
    return invoice
