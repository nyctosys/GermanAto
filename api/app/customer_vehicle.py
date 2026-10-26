"""Customer & vehicle helpers: serialize, phone lookup, balances, reuse on intake."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.foundation.validation import normalize_pk_phone, normalize_reg_no
from app.invoice_math import invoice_amount_due, invoice_amount_paid
from app.models import Car, Customer, Invoice, RepairOrder

CUSTOMER_TYPES = (
    "retail",
    "fleet",
    "insurance",
    "corporate",
    "walk_in",
    "other",
)

# Roles that may create/update customers and vehicles (reception + ops).
CUSTOMER_WRITE_ROLES = [
    "admin",
    "owner",
    "manager",
    "accountant",
    "service_advisor",
    "inventory_manager",
    "store_keeper",
]


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def customer_dict(c: Customer, *, include_vehicles: bool = False) -> dict:
    data = {
        "id": c.id,
        "code": c.code,
        "name": c.name,
        "phone": c.phone,
        "alternate_phone": getattr(c, "alternate_phone", None),
        "address": c.address,
        "customer_type": getattr(c, "customer_type", None) or "retail",
        "notes": getattr(c, "notes", None),
        "consent_whatsapp": bool(getattr(c, "consent_whatsapp", False)),
        "consent_sms": bool(getattr(c, "consent_sms", False)),
        "consent_call": bool(getattr(c, "consent_call", True)),
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
        "created_by_user": getattr(c, "created_by_user", None),
        "updated_by_user": getattr(c, "updated_by_user", None),
        "version": getattr(c, "version", None),
    }
    if include_vehicles:
        cars = getattr(c, "cars", None) or []
        data["vehicles"] = [car_dict(car) for car in cars if getattr(car, "deleted_at", None) is None]
        data["vehicle_count"] = len(data["vehicles"])
    return data


def car_dict(car: Car) -> dict:
    cust = car.customer
    return {
        "id": car.id,
        "code": car.code,
        "make": car.make,
        "model": car.model,
        "year": getattr(car, "year", None),
        "plate_no": car.plate_no,
        "mileage": car.mileage,
        "vin": car.vin,
        "color": car.color,
        "chasis_no": car.chasis_no,
        "engine_no": getattr(car, "engine_no", None),
        "notes": getattr(car, "notes", None),
        "customer_id": car.customer_id,
        "customer_name": cust.name if cust else None,
        "customer_code": cust.code if cust else None,
        "customer_phone": cust.phone if cust else None,
        "customer_address": cust.address if cust else None,
        "created_at": _iso(car.created_at),
        "updated_at": _iso(car.updated_at),
        "created_by_user": getattr(car, "created_by_user", None),
        "updated_by_user": getattr(car, "updated_by_user", None),
        "version": getattr(car, "version", None),
    }


def normalize_phone_safe(value: str | None) -> str | None:
    if value is None or str(value).strip() in ("", "N/A"):
        return None
    try:
        return normalize_pk_phone(str(value))
    except ValueError:
        return str(value).strip()


def find_customers_by_phone(db: Session, phone: str, *, limit: int = 10) -> list[Customer]:
    """Exact + alternate match after normalization; falls back to suffix contains."""
    normalized = normalize_phone_safe(phone)
    if not normalized and not (phone or "").strip():
        return []
    q = db.query(Customer)
    clauses = []
    if normalized:
        clauses.append(Customer.phone == normalized)
        clauses.append(Customer.alternate_phone == normalized)
        digits = normalized.replace("+", "")
        if len(digits) >= 10:
            clauses.append(Customer.phone.ilike(f"%{digits[-10:]}%"))
            clauses.append(Customer.alternate_phone.ilike(f"%{digits[-10:]}%"))
    raw = (phone or "").strip()
    if raw and raw != normalized:
        clauses.append(Customer.phone.ilike(f"%{raw}%"))
        clauses.append(Customer.alternate_phone.ilike(f"%{raw}%"))
    if not clauses:
        return []
    return q.filter(or_(*clauses)).order_by(Customer.id.desc()).limit(limit).all()


def find_duplicate_customers(db: Session, *, phone: str | None, name: str | None = None) -> list[Customer]:
    matches: list[Customer] = []
    seen: set[int] = set()
    if phone:
        for c in find_customers_by_phone(db, phone):
            if c.id not in seen:
                seen.add(c.id)
                matches.append(c)
    if name and str(name).strip() and str(name).strip() != "N/A":
        for c in (
            db.query(Customer)
            .filter(Customer.name.ilike(str(name).strip()))
            .limit(5)
            .all()
        ):
            if c.id not in seen:
                seen.add(c.id)
                matches.append(c)
    return matches


def find_existing_car(
    db: Session,
    *,
    car_id: int | None = None,
    plate_no: str | None = None,
    vin: str | None = None,
    customer_id: int | None = None,
) -> Car | None:
    if car_id:
        found = db.get(Car, int(car_id))
        if found and getattr(found, "deleted_at", None) is None:
            return found
    try:
        plate = normalize_reg_no(plate_no) if plate_no else None
    except ValueError:
        plate = (plate_no or "").strip().upper() or None
    vin_clean = (vin or "").strip().upper() or None
    if vin_clean:
        hit = db.query(Car).filter(Car.vin == vin_clean).first()
        if hit:
            return hit
    if plate:
        q = db.query(Car).filter(Car.plate_no == plate)
        if customer_id:
            owned = q.filter(Car.customer_id == customer_id).first()
            if owned:
                return owned
        matches = q.limit(2).all()
        if len(matches) == 1:
            return matches[0]
        if customer_id and matches:
            for m in matches:
                if m.customer_id == customer_id:
                    return m
    return None


def customer_activity_summary(db: Session, customer_id: int) -> dict:
    """Previous repairs, estimates, invoices, and outstanding balance."""
    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer_id, Invoice.type_of == "invoice")
        .order_by(Invoice.created_at.desc())
        .limit(20)
        .all()
    )
    quotes = (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer_id, Invoice.type_of == "quote")
        .order_by(Invoice.created_at.desc())
        .limit(20)
        .all()
    )
    repairs = (
        db.query(RepairOrder)
        .filter(RepairOrder.customer_id == customer_id)
        .order_by(RepairOrder.created_at.desc())
        .limit(20)
        .all()
    )

    receivable = 0.0
    open_invoices = []
    for inv in (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer_id, Invoice.type_of == "invoice")
        .all()
    ):
        owed = round(invoice_amount_due(inv) - invoice_amount_paid(inv), 2)
        if owed > 0:
            receivable += owed
            open_invoices.append(
                {
                    "id": inv.id,
                    "document_no": inv.document_no,
                    "net_total": float(inv.net_total or 0),
                    "owed": owed,
                    "status": inv.status,
                    "created_at": _iso(inv.created_at),
                }
            )

    def _inv_row(inv: Invoice) -> dict:
        return {
            "id": inv.id,
            "document_no": inv.document_no,
            "type_of": inv.type_of,
            "net_total": float(inv.net_total or 0),
            "status": inv.status,
            "created_at": _iso(inv.created_at),
            "owed": round(invoice_amount_due(inv) - invoice_amount_paid(inv), 2),
        }

    def _ro_row(ro: RepairOrder) -> dict:
        return {
            "id": ro.id,
            "document_no": ro.document_no,
            "customer_reg_no": ro.customer_reg_no,
            "current_status": ro.current_status,
            "created_at": _iso(ro.created_at),
            "problem_description": (ro.problem_description or "")[:120],
        }

    return {
        "receivable_total": round(receivable, 2),
        "open_invoice_count": len(open_invoices),
        "open_invoices": open_invoices[:10],
        "recent_invoices": [_inv_row(i) for i in invoices],
        "recent_estimates": [_inv_row(q) for q in quotes],
        "recent_repairs": [_ro_row(r) for r in repairs],
        "counts": {
            "invoices": db.query(Invoice)
            .filter(Invoice.customer_id == customer_id, Invoice.type_of == "invoice")
            .count(),
            "estimates": db.query(Invoice)
            .filter(Invoice.customer_id == customer_id, Invoice.type_of == "quote")
            .count(),
            "repairs": db.query(RepairOrder)
            .filter(RepairOrder.customer_id == customer_id)
            .count(),
            "vehicles": db.query(Car).filter(Car.customer_id == customer_id).count(),
        },
    }


def load_customer_bundle(db: Session, customer_id: int) -> dict | None:
    customer = (
        db.query(Customer)
        .options(joinedload(Customer.cars))
        .filter(Customer.id == customer_id)
        .first()
    )
    if not customer or getattr(customer, "deleted_at", None) is not None:
        return None
    return {
        "customer": customer_dict(customer, include_vehicles=True),
        "activity": customer_activity_summary(db, customer_id),
    }
