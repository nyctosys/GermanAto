"""Job card CRUD + pull lines into a quotation."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_
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
    Visit,
    Worker,
)
from app.pipeline import assert_can_create_job_card, assert_quote_from_job_card, discount_pct
from app.foundation.overrides import assert_discount_override
from app.document_links import apply_links
from app.document_numbers import job_card_document_no
from app.invoice_math import calculate_invoice_status, calculate_totals


LINE_STATUSES = {"Pending", "Approved", "Rejected", "In progress", "Done", "QC passed"}
PAY_TYPES = {"customer", "warranty", "internal"}
STATUSES = {"draft", "open", "quoted", "closed", "cancelled"}
PRIORITIES = {"low", "normal", "high", "urgent"}


def _parse_dt(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}")


def _enrich(card: JobCard, db: Session) -> dict:
    data = card.to_dict()
    if card.worker_id:
        w = db.get(Worker, card.worker_id)
        if w:
            data["worker_name"] = f"{w.first_name or ''} {w.last_name or ''}".strip()
            data["worker_employee_id"] = w.employee_id
    return data


def create_job_card(db: Session, data: dict, user) -> JobCard:
    from app.document_links import resolve_car, resolve_customer
    from app.customer_vehicle import find_existing_car

    car_id = data.get("car_id")
    visit_id = data.get("visit_id")
    car_id_i = int(car_id) if car_id not in (None, "") else None
    visit_id_i = int(visit_id) if visit_id not in (None, "") else None

    customer_name = str(data.get("customer_name") or "").strip()
    customer_phone = str(data.get("customer_phone") or "").strip()
    customer_reg_no = str(data.get("customer_reg_no") or "").strip()
    customer_made = str(data.get("customer_made") or "").strip()

    status = str(data.get("status") or "open").strip().lower()
    if status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    priority = str(data.get("priority") or "normal").strip().lower()
    if priority not in PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    # Reuse permanent customer/vehicle IDs — never invent duplicates on open.
    customer = resolve_customer(
        db,
        data.get("customer_id"),
        customer_name or None,
        customer_phone or None,
    )
    car = resolve_car(
        db,
        car_id_i,
        customer_reg_no or None,
        None,
        customer.id if customer else None,
    )
    if car is None and customer_reg_no:
        car = find_existing_car(
            db,
            plate_no=customer_reg_no,
            customer_id=customer.id if customer else None,
        )
    if car is not None and customer is None and car.customer_id:
        customer = resolve_customer(db, car.customer_id, None, None)
    if car is not None:
        car_id_i = car.id
        if not customer_reg_no and car.plate_no:
            customer_reg_no = car.plate_no
        if not customer_made and (car.make or car.model):
            customer_made = f"{car.make or ''} {car.model or ''}".strip()
    if customer is not None:
        if not customer_name and customer.name:
            customer_name = customer.name
        if not customer_phone and customer.phone:
            customer_phone = customer.phone

    if not customer_name and status != "draft":
        raise HTTPException(status_code=400, detail="Customer name is required")

    # Draft may skip visit gate; open/quoted still require check-in when car linked.
    if status != "draft":
        assert_can_create_job_card(db, car_id=car_id_i, visit_id=visit_id_i)

    # Prefill intake fields from visit when linked.
    odometer = str(data.get("odometer") or "").strip() or None
    fuel_level = str(data.get("fuel_level") or "").strip() or None
    problem = str(data.get("problem_description") or "").strip() or None
    inspection_notes = str(data.get("inspection_notes") or "").strip() or None
    intake_at = _parse_dt(data.get("intake_at")) or datetime.utcnow()
    if visit_id_i:
        visit = db.get(Visit, visit_id_i)
        if visit:
            odometer = odometer or visit.odometer
            fuel_level = fuel_level or visit.fuel_level
            problem = problem or visit.reported_complaints
            inspection_notes = inspection_notes or visit.existing_damage
            if visit.check_in_at and not data.get("intake_at"):
                intake_at = visit.check_in_at

    worker_id = data.get("worker_id")
    worker_id_i = int(worker_id) if worker_id not in (None, "") else None
    if worker_id_i:
        w = db.get(Worker, worker_id_i)
        if not w or getattr(w, "deleted_at", None) is not None:
            raise HTTPException(status_code=400, detail="Assigned worker not found")

    card = JobCard(
        visit_id=visit_id_i,
        car_id=car_id_i,
        customer_id=customer.id if customer else (
            int(data["customer_id"]) if data.get("customer_id") else None
        ),
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_reg_no=customer_reg_no,
        customer_made=customer_made,
        notes=data.get("notes"),
        status=status,
        priority=priority,
        expected_completion_at=_parse_dt(data.get("expected_completion_at")),
        intake_at=intake_at,
        worker_id=worker_id_i,
        team_name=str(data.get("team_name") or "").strip() or None,
        problem_description=problem,
        inspection_notes=inspection_notes,
        odometer=odometer,
        fuel_level=fuel_level,
        created_by_user=getattr(user, "username", None),
    )
    db.add(card)
    db.flush()
    if not card.document_no:
        card.document_no = job_card_document_no(card.id)
    for raw in data.get("lines") or []:
        db.add(_build_line(db, card.id, raw))
    db.flush()
    audit_write(
        db,
        user=user,
        action="CREATE",
        module="job_cards",
        reference_id=card.id,
        details=f"Job card {card.document_no} for {card.customer_name}",
        new_value=card.to_dict(),
    )
    return card


def update_job_card(db: Session, card: JobCard, data: dict, user) -> JobCard:
    old = card.to_dict()
    if "status" in data and data["status"] is not None:
        status = str(data["status"]).strip().lower()
        if status not in STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        # Promoting draft → open enforces visit gate.
        if card.status == "draft" and status != "draft":
            assert_can_create_job_card(db, car_id=card.car_id, visit_id=card.visit_id)
        card.status = status
    if "priority" in data and data["priority"] is not None:
        priority = str(data["priority"]).strip().lower()
        if priority not in PRIORITIES:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")
        card.priority = priority

    for f in (
        "customer_name",
        "customer_phone",
        "customer_reg_no",
        "customer_made",
        "notes",
        "team_name",
        "problem_description",
        "inspection_notes",
        "odometer",
        "fuel_level",
    ):
        if f in data:
            val = data[f]
            setattr(card, f, (str(val).strip() or None) if val is not None else None)

    if "expected_completion_at" in data:
        card.expected_completion_at = _parse_dt(data.get("expected_completion_at"))
    if "intake_at" in data:
        card.intake_at = _parse_dt(data.get("intake_at")) or card.intake_at

    if "worker_id" in data:
        wid = data.get("worker_id")
        if wid in (None, ""):
            card.worker_id = None
        else:
            w = db.get(Worker, int(wid))
            if not w or getattr(w, "deleted_at", None) is not None:
                raise HTTPException(status_code=400, detail="Assigned worker not found")
            card.worker_id = w.id

    if "visit_id" in data:
        card.visit_id = int(data["visit_id"]) if data["visit_id"] not in (None, "") else None
    if "customer_id" in data and data["customer_id"] not in (None, ""):
        card.customer_id = int(data["customer_id"])
    if "car_id" in data and data["car_id"] not in (None, ""):
        card.car_id = int(data["car_id"])

    if "lines" in data:
        replace_lines(db, card, data["lines"] or [])

    db.flush()
    audit_write(
        db,
        user=user,
        action="UPDATE",
        module="job_cards",
        reference_id=card.id,
        details=f"Updated job card {card.document_no or card.id}",
        old_value=old,
        new_value=card.to_dict(),
        reason=data.get("reason"),
    )
    return card


def list_job_cards(
    db: Session,
    *,
    q: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[JobCard]:
    query = db.query(JobCard).filter(JobCard.deleted_at.is_(None))
    if status:
        query = query.filter(JobCard.status == status.strip().lower())
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        filters = [
            JobCard.customer_name.ilike(like),
            JobCard.customer_phone.ilike(like),
            JobCard.customer_reg_no.ilike(like),
            JobCard.customer_made.ilike(like),
            JobCard.problem_description.ilike(like),
            JobCard.document_no.ilike(like),
            JobCard.notes.ilike(like),
        ]
        if term.isdigit():
            filters.append(JobCard.id == int(term))
        query = query.filter(or_(*filters))
    return query.order_by(JobCard.id.desc()).limit(min(500, max(1, limit))).all()


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
    # Estimates are not revenue: do not store cash on Invoice.advance.
    # Required advance is computed; received advances use CustomerDeposit liabilities.
    advance = 0.0
    include_tax = bool(data.get("include_tax", False))
    tax_amount = float(data.get("tax_amount") or 0)
    if include_tax and not tax_amount and data.get("include_tax"):
        tax_amount = round(total * 0.17, 2)
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
        customer_mileage=str(data.get("customer_mileage") or card.odometer or ""),
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
        approval_state="draft",
        created_by_user=getattr(user, "username", None),
        visit_id=card.visit_id,
        job_card_id=card.id,
        customer_id=card.customer_id,
        car_id=card.car_id,
    )
    apply_links(db, invoice, {**data, "customer_id": card.customer_id, "car_id": card.car_id})
    db.add(invoice)
    db.flush()
    from app.estimates import stamp_quote_from_job_card

    stamp_quote_from_job_card(db, invoice, card, data)
    # Recompute balance after tax/required_advance stamp (advance remains 0 on quote)
    if invoice.include_tax:
        invoice.balance = round(
            float(invoice.net_total or 0)
            + float(invoice.tax_amount or 0)
            - float(invoice.discount or 0),
            2,
        )
    else:
        invoice.balance = round(
            float(invoice.net_total or 0) - float(invoice.discount or 0),
            2,
        )

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
