"""Car ownership transfer + unified car history timeline."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.foundation.attachments import save_evidence
from app.foundation.audit import audit_write
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import get_branch
from app.models import (
    Car,
    CarOwnership,
    CashReceived,
    Customer,
    Invoice,
    RepairOrder,
)


def _active_customer(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None or getattr(customer, "deleted_at", None) is not None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def transfer_car_ownership(
    db: Session,
    *,
    car: Car,
    to_customer_id: int,
    transfer_date: date,
    reason: str,
    evidence_file,
    user,
    branch_id: str | None = None,
) -> CarOwnership:
    """Transfer car to another customer. Evidence file is required."""
    reason = (reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if evidence_file is None or not getattr(evidence_file, "filename", None):
        raise HTTPException(status_code=400, detail="evidence attachment is required")

    to_customer = _active_customer(db, int(to_customer_id))
    from_id = car.customer_id
    if from_id is not None and int(from_id) == int(to_customer.id):
        raise HTTPException(
            status_code=400,
            detail="Cannot transfer a car to the same owner",
        )

    bid = branch_id or get_branch() or DEFAULT_BRANCH_ID
    by = getattr(user, "username", None) if user else None

    # Save evidence first (entity_id filled after ownership row exists)
    evidence = save_evidence(
        db,
        evidence_file,
        entity_type="car_ownership",
        entity_id=None,
        branch_id=bid,
        uploaded_by=by,
        notes=f"Ownership transfer evidence for car {car.id}",
    )
    if not evidence:
        raise HTTPException(status_code=400, detail="evidence attachment is required")

    ownership = CarOwnership(
        car_id=car.id,
        from_customer_id=from_id,
        to_customer_id=to_customer.id,
        transfer_date=transfer_date,
        reason=reason,
        evidence_attachment_id=evidence["id"],
        transferred_by=by,
        branch_id=bid,
    )
    db.add(ownership)
    db.flush()

    # Link attachment to ownership row
    from app.models import Attachment

    att = db.get(Attachment, evidence["id"])
    if att:
        att.entity_id = ownership.id

    old_owner = from_id
    car.customer_id = to_customer.id
    if hasattr(car, "version") and car.version is not None:
        car.version = int(car.version or 1) + 1

    audit_write(
        db,
        user=user,
        action="TRANSFER",
        module="car",
        reference_id=car.id,
        details=(
            f"Transferred car {car.id} from customer {old_owner} "
            f"to {to_customer.id}: {reason}"
        ),
        old_value={"customer_id": old_owner},
        new_value={"customer_id": to_customer.id, "ownership_id": ownership.id},
        reason=reason,
        branch_id=bid,
    )
    db.flush()
    return ownership


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _event(
    *,
    kind: str,
    when,
    title: str,
    summary: str = "",
    href: str | None = None,
    meta: dict | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "at": _iso(when),
        "title": title,
        "summary": summary,
        "href": href,
        "meta": meta or {},
    }


def build_car_history(
    db: Session,
    car_id: int,
    *,
    kinds: set[str] | None = None,
) -> dict[str, Any]:
    """Unified timeline for one car (newest first)."""
    car = (
        db.query(Car)
        .options(joinedload(Car.customer))
        .filter(Car.id == car_id)
        .first()
    )
    if car is None or getattr(car, "deleted_at", None) is not None:
        raise HTTPException(status_code=404, detail="Car not found")

    events: list[dict[str, Any]] = []
    want = kinds

    # Ownership transfers
    if want is None or "ownership" in want:
        transfers = (
            db.query(CarOwnership)
            .options(
                joinedload(CarOwnership.from_customer),
                joinedload(CarOwnership.to_customer),
                joinedload(CarOwnership.evidence),
            )
            .filter(CarOwnership.car_id == car_id)
            .order_by(CarOwnership.transfer_date.desc(), CarOwnership.id.desc())
            .all()
        )
        for row in transfers:
            events.append(
                _event(
                    kind="ownership",
                    when=datetime.combine(row.transfer_date, datetime.min.time())
                    if row.transfer_date
                    else row.created_at,
                    title="Ownership transfer",
                    summary=(
                        f"{row.from_customer.name if row.from_customer else 'Unassigned'} → "
                        f"{row.to_customer.name if row.to_customer else row.to_customer_id}"
                    ),
                    href=f"/cars/{car_id}",
                    meta=row.to_dict(),
                )
            )

    # Invoices / quotes
    if want is None or "quote" in want or "invoice" in want or "payment" in want:
        invoices = (
            db.query(Invoice)
            .filter(Invoice.car_id == car_id)
            .order_by(Invoice.created_at.desc(), Invoice.id.desc())
            .all()
        )
        for inv in invoices:
            doc_type = (inv.type_of or "invoice").lower()
            kind = "quote" if doc_type == "quote" else "invoice"
            if want is not None and kind not in want and "payment" not in (want or set()):
                pass
            else:
                if want is None or kind in want:
                    events.append(
                        _event(
                            kind=kind,
                            when=inv.created_at,
                            title=f"{kind.title()} #{inv.id}",
                            summary=(
                                f"{inv.customer_name} · "
                                f"{float(inv.net_total or 0):,.2f} PKR · "
                                f"odometer {inv.customer_mileage or '—'}"
                            ),
                            href=f"/invoices/{inv.id}/edit"
                            if kind == "invoice"
                            else "/quotes/pending",
                            meta={
                                "id": inv.id,
                                "type_of": inv.type_of,
                                "status": inv.status,
                                "net_total": inv.net_total,
                                "balance": inv.balance,
                                "odometer": inv.customer_mileage,
                                "customer_id": inv.customer_id,
                                "customer_name": inv.customer_name,
                            },
                        )
                    )

            # Payments on this invoice (history stays with original customer snapshot)
            if want is None or "payment" in want:
                receipts = (
                    db.query(CashReceived)
                    .filter(CashReceived.invoice_id == inv.id)
                    .order_by(CashReceived.date.desc(), CashReceived.id.desc())
                    .all()
                )
                for cash in receipts:
                    events.append(
                        _event(
                            kind="payment",
                            when=datetime.combine(cash.date, datetime.min.time())
                            if cash.date
                            else cash.created_at,
                            title=f"Payment on invoice #{inv.id}",
                            summary=(
                                f"{float(cash.amount or 0):,.2f} PKR via {cash.payment_method}"
                            ),
                            href="/finance/cash-received",
                            meta={
                                "id": cash.id,
                                "invoice_id": inv.id,
                                "amount": cash.amount,
                                "payment_method": cash.payment_method,
                            },
                        )
                    )
                # Also parse payments_history JSON if present
                if inv.payments_history:
                    try:
                        history = json.loads(inv.payments_history) or []
                    except (TypeError, ValueError):
                        history = []
                    for pay in history:
                        if pay.get("source") == "cash_received":
                            continue  # already covered
                        events.append(
                            _event(
                                kind="payment",
                                when=pay.get("timestamp") or inv.updated_at or inv.created_at,
                                title=f"Payment on invoice #{inv.id}",
                                summary=(
                                    f"{float(pay.get('amount') or 0):,.2f} PKR "
                                    f"({pay.get('person') or 'system'})"
                                ),
                                href=f"/invoices/{inv.id}/edit",
                                meta={"invoice_id": inv.id, **pay},
                            )
                        )

    # Repair orders + parts + technician
    if want is None or "repair_order" in want or "parts" in want:
        orders = (
            db.query(RepairOrder)
            .options(joinedload(RepairOrder.parts))
            .filter(RepairOrder.car_id == car_id)
            .order_by(RepairOrder.created_at.desc(), RepairOrder.id.desc())
            .all()
        )
        for ro in orders:
            if want is None or "repair_order" in want:
                events.append(
                    _event(
                        kind="repair_order",
                        when=ro.created_at,
                        title=f"Repair order #{ro.id}",
                        summary=(
                            f"{ro.current_status} · tech {ro.worker_name or '—'} · "
                            f"odometer {ro.customer_mileage or '—'}"
                        ),
                        href="/repair-orders",
                        meta={
                            "id": ro.id,
                            "status": ro.current_status,
                            "technician": ro.worker_name,
                            "odometer": ro.customer_mileage,
                            "problem": ro.problem_description,
                        },
                    )
                )
            if want is None or "parts" in want:
                for part in ro.parts or []:
                    events.append(
                        _event(
                            kind="parts",
                            when=ro.created_at,
                            title=f"Part on RO #{ro.id}",
                            summary=(
                                f"{part.description} × {part.quantity} ({part.status})"
                            ),
                            href="/repair-orders",
                            meta={
                                "repair_order_id": ro.id,
                                "part_id": part.id,
                                "description": part.description,
                                "quantity": part.quantity,
                                "part_number": part.part_number,
                                "status": part.status,
                            },
                        )
                    )

    def sort_key(ev: dict) -> tuple:
        at = ev.get("at") or ""
        return (str(at),)

    events.sort(key=sort_key, reverse=True)

    return {
        "car": {
            "id": car.id,
            "make": car.make,
            "model": car.model,
            "plate_no": car.plate_no,
            "vin": car.vin,
            "mileage": car.mileage,
            "color": car.color,
            "customer_id": car.customer_id,
            "customer_name": car.customer.name if car.customer else None,
            "customer_phone": car.customer.phone if car.customer else None,
        },
        "events": events,
        "count": len(events),
    }


def find_cars_for_history_search(db: Session, q: str) -> list[Car]:
    """Search cars by plate, VIN, make/model, or customer name/phone."""
    from sqlalchemy import or_

    term = f"%{(q or '').strip()}%"
    if term == "%%":
        return []
    return (
        db.query(Car)
        .outerjoin(Customer, Car.customer_id == Customer.id)
        .options(joinedload(Car.customer))
        .filter(
            or_(
                Car.plate_no.ilike(term),
                Car.vin.ilike(term),
                Car.make.ilike(term),
                Car.model.ilike(term),
                Customer.name.ilike(term),
                Customer.phone.ilike(term),
            )
        )
        .order_by(Car.id.desc())
        .limit(50)
        .all()
    )
