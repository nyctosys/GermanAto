"""Shared entity search, duplicate checks, and gate-pass APIs.

Reuses existing models and document_links; does not replace per-domain routers.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.document_links import resolve_car, resolve_customer
from app.document_numbers import worker_display_code
from app.foundation.idempotent import idempotent_create
from app.foundation.validation import normalize_pk_phone, normalize_reg_no
from app.models import (
    Car,
    Customer,
    YardGatePass,
    Inventory,
    Vendor,
    Worker,
)
from app.search_suggestions import suggestions_for

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/entities", tags=["entities"])

ENTITY_TYPES = ("customer", "car", "worker", "vendor", "inventory")


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


def _customer_row(c: Customer) -> dict:
    return {
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
        "label": f"{c.code or ''} · {c.name or ''} · {c.phone or ''}".strip(" ·"),
        "entity_type": "customer",
    }


def _car_row(car: Car) -> dict:
    cust = car.customer
    year = getattr(car, "year", None)
    return {
        "id": car.id,
        "code": car.code,
        "make": car.make,
        "model": car.model,
        "year": year,
        "plate_no": car.plate_no,
        "vin": car.vin,
        "mileage": car.mileage,
        "color": car.color,
        "chasis_no": car.chasis_no,
        "engine_no": getattr(car, "engine_no", None),
        "notes": getattr(car, "notes", None),
        "customer_id": car.customer_id,
        "customer_name": cust.name if cust else None,
        "customer_phone": cust.phone if cust else None,
        "customer_address": cust.address if cust else None,
        "customer_code": cust.code if cust else None,
        "label": (
            f"{car.code or ''} · {car.plate_no or ''} · "
            f"{(car.make or '')} {(car.model or '')}".strip()
            + (f" {year}" if year else "")
        ).strip(" ·"),
        "entity_type": "car",
    }


def _worker_row(w: Worker) -> dict:
    name = f"{w.first_name or ''} {w.last_name or ''}".strip()
    return {
        "id": w.id,
        "code": worker_display_code(w.employee_id, w.id),
        "employee_id": w.employee_id,
        "name": name,
        "phone": w.phone,
        "cnic": w.cnic,
        "position": w.position,
        "department": w.department,
        "status": w.status,
        "label": f"{w.employee_id or w.id} · {name} · {w.position or ''}".strip(" ·"),
        "entity_type": "worker",
    }


def _vendor_row(v: Vendor) -> dict:
    return {
        "id": v.id,
        "code": v.code,
        "name": v.name,
        "company_name": v.company_name,
        "phone": v.phone,
        "email": v.email,
        "cnic": v.cnic,
        "payment_terms_days": int(getattr(v, "payment_terms_days", None) or 30),
        "label": f"{v.code or ''} · {v.name} · {v.company_name or ''}".strip(" ·"),
        "entity_type": "vendor",
    }


def _inventory_row(item: Inventory) -> dict:
    on_hand = int(item.quantity or 0)
    reserved = int(getattr(item, "reserved", 0) or 0)
    return {
        "id": item.id,
        "code": item.part_number,
        "part_number": item.part_number,
        "barcode": item.barcode,
        "name": item.name,
        "category": item.category,
        "unit": getattr(item, "unit", None) or "pcs",
        "quantity": on_hand,
        "available": on_hand - reserved,
        "price": float(item.price or 0),
        "avg_cost": float(getattr(item, "avg_cost", 0) or 0),
        "preferred_vendor_id": getattr(item, "preferred_vendor_id", None),
        "pending_purchase": bool(getattr(item, "pending_purchase", False)),
        "label": f"{item.part_number} · {item.name} · avail {on_hand - reserved}",
        "entity_type": "inventory",
    }


def _search_customers(db: Session, q: str, limit: int) -> list[dict]:
    rows = (
        db.query(Customer)
        .filter(
            or_(
                Customer.name.ilike(f"%{q}%"),
                Customer.phone.ilike(f"%{q}%"),
                Customer.alternate_phone.ilike(f"%{q}%"),
                Customer.address.ilike(f"%{q}%"),
                Customer.code.ilike(f"%{q}%"),
            )
        )
        .order_by(Customer.name)
        .limit(limit)
        .all()
    )
    return [_customer_row(c) for c in rows]


def _search_cars(db: Session, q: str, limit: int, customer_id: int | None = None) -> list[dict]:
    query = db.query(Car)
    if customer_id:
        query = query.filter(Car.customer_id == customer_id)
    query = query.filter(
        or_(
            Car.plate_no.ilike(f"%{q}%"),
            Car.vin.ilike(f"%{q}%"),
            Car.make.ilike(f"%{q}%"),
            Car.model.ilike(f"%{q}%"),
            Car.code.ilike(f"%{q}%"),
            Car.chasis_no.ilike(f"%{q}%"),
        )
    )
    rows = query.order_by(Car.plate_no).limit(limit).all()
    return [_car_row(c) for c in rows]


def _search_workers(db: Session, q: str, limit: int) -> list[dict]:
    rows = (
        db.query(Worker)
        .filter(
            or_(
                Worker.first_name.ilike(f"%{q}%"),
                Worker.last_name.ilike(f"%{q}%"),
                Worker.employee_id.ilike(f"%{q}%"),
                Worker.phone.ilike(f"%{q}%"),
                Worker.cnic.ilike(f"%{q}%"),
            )
        )
        .order_by(Worker.first_name)
        .limit(limit)
        .all()
    )
    return [_worker_row(w) for w in rows]


def _search_vendors(db: Session, q: str, limit: int) -> list[dict]:
    rows = (
        db.query(Vendor)
        .filter(
            or_(
                Vendor.name.ilike(f"%{q}%"),
                Vendor.company_name.ilike(f"%{q}%"),
                Vendor.phone.ilike(f"%{q}%"),
                Vendor.code.ilike(f"%{q}%"),
                Vendor.cnic.ilike(f"%{q}%"),
            )
        )
        .order_by(Vendor.name)
        .limit(limit)
        .all()
    )
    return [_vendor_row(v) for v in rows]


def _search_inventory(db: Session, q: str, limit: int) -> list[dict]:
    rows = (
        db.query(Inventory)
        .filter(
            or_(
                Inventory.name.ilike(f"%{q}%"),
                Inventory.part_number.ilike(f"%{q}%"),
                Inventory.barcode.ilike(f"%{q}%"),
                Inventory.manufacturer_part_number.ilike(f"%{q}%"),
                Inventory.alternate_codes.ilike(f"%{q}%"),
            )
        )
        .order_by(Inventory.name)
        .limit(limit)
        .all()
    )
    return [_inventory_row(i) for i in rows]


@router.get("/search")
def search_entities(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    q: str = Query("", min_length=0),
    type: str = Query("customer", alias="type"),
    limit: int = Query(20, ge=1, le=50),
    customer_id: int | None = Query(None),
):
    """Searchable selector feed for customer / car / worker / vendor / inventory."""
    entity = (type or "customer").strip().lower()
    if entity not in ENTITY_TYPES:
        return _json({"error": f"type must be one of {ENTITY_TYPES}"}, 400)
    query = (q or "").strip()
    if len(query) < 1:
        # Empty query → recent / first page for picker defaults
        if entity == "customer":
            rows = [_customer_row(c) for c in db.query(Customer).order_by(Customer.id.desc()).limit(limit)]
        elif entity == "car":
            qq = db.query(Car)
            if customer_id:
                qq = qq.filter(Car.customer_id == customer_id)
            rows = [_car_row(c) for c in qq.order_by(Car.id.desc()).limit(limit)]
        elif entity == "worker":
            rows = [
                _worker_row(w)
                for w in db.query(Worker).filter(Worker.status == "active").order_by(Worker.id.desc()).limit(limit)
            ]
        elif entity == "vendor":
            rows = [_vendor_row(v) for v in db.query(Vendor).order_by(Vendor.id.desc()).limit(limit)]
        else:
            rows = [_inventory_row(i) for i in db.query(Inventory).order_by(Inventory.id.desc()).limit(limit)]
        return _json({"query": query, "type": entity, "results": rows, "count": len(rows)}, 200)

    searchers = {
        "customer": lambda: _search_customers(db, query, limit),
        "car": lambda: _search_cars(db, query, limit, customer_id),
        "worker": lambda: _search_workers(db, query, limit),
        "vendor": lambda: _search_vendors(db, query, limit),
        "inventory": lambda: _search_inventory(db, query, limit),
    }
    results = searchers[entity]()
    payload: dict[str, Any] = {
        "query": query,
        "type": entity,
        "results": results,
        "count": len(results),
    }
    if not results:
        if entity == "customer":
            corpus = [r[0] for r in db.query(Customer.name).distinct().all() if r[0]]
        elif entity == "car":
            corpus = [r[0] for r in db.query(Car.plate_no).distinct().all() if r[0]]
        elif entity == "worker":
            corpus = [f"{w.first_name} {w.last_name}" for w in db.query(Worker).limit(200)]
        elif entity == "vendor":
            corpus = [r[0] for r in db.query(Vendor.name).distinct().all() if r[0]]
        else:
            corpus = [r[0] for r in db.query(Inventory.name).distinct().all() if r[0]]
        payload.update(suggestions_for(query, corpus))
    return _json(payload, 200)


@router.get("/customers/{customer_id:int}")
def get_customer_bundle(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Customer + their vehicles for job-card / invoice auto-populate."""
    from app.customer_vehicle import customer_activity_summary

    customer = db.get(Customer, customer_id)
    if not customer or getattr(customer, "deleted_at", None) is not None:
        return _json({"error": "Customer not found"}, 404)
    cars = db.query(Car).filter_by(customer_id=customer_id).order_by(Car.plate_no).all()
    return _json(
        {
            "customer": _customer_row(customer),
            "vehicles": [_car_row(c) for c in cars],
            "count": len(cars),
            "activity": customer_activity_summary(db, customer_id),
        },
        200,
    )


@router.post("/check-duplicate")
def check_duplicate(
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(get_current_user),
):
    """Warn staff before creating a likely duplicate record."""
    data = body or {}
    entity = (data.get("type") or data.get("entity_type") or "").strip().lower()
    matches: list[dict] = []
    warnings: list[str] = []

    if entity == "customer":
        from app.customer_vehicle import find_duplicate_customers

        phone = data.get("phone") or data.get("alternate_phone")
        name = (data.get("name") or "").strip() or None
        try:
            if phone:
                phone = normalize_pk_phone(str(phone))
        except Exception:
            phone = (phone or "").strip()
        exclude_id = data.get("exclude_id")
        for c in find_duplicate_customers(db, phone=phone, name=name):
            if exclude_id and c.id == int(exclude_id):
                continue
            matches.append(_customer_row(c))
            warnings.append(
                f"Possible duplicate: {c.code or c.id} · {c.name} · {c.phone}"
            )

    elif entity == "car":
        plate = data.get("plate_no") or data.get("reg_no")
        vin = (data.get("vin") or "").strip()
        try:
            if plate:
                plate = normalize_reg_no(str(plate))
        except Exception:
            plate = (plate or "").strip()
        exclude_id = data.get("exclude_id")
        q = db.query(Car)
        if exclude_id:
            q = q.filter(Car.id != int(exclude_id))
        if plate:
            for c in q.filter(Car.plate_no == plate).limit(5):
                matches.append(_car_row(c))
                warnings.append(f"Vehicle with plate {plate} already exists ({c.code})")
        if vin:
            for c in q.filter(Car.vin == vin).limit(5):
                matches.append(_car_row(c))
                warnings.append(f"Vehicle with VIN {vin} already exists ({c.code})")

    elif entity == "vendor":
        phone = (data.get("phone") or "").strip()
        cnic = (data.get("cnic") or "").strip()
        exclude_id = data.get("exclude_id")
        q = db.query(Vendor)
        if exclude_id:
            q = q.filter(Vendor.id != int(exclude_id))
        if phone:
            for v in q.filter(Vendor.phone == phone).limit(5):
                matches.append(_vendor_row(v))
                warnings.append(f"Vendor with phone {phone} already exists ({v.code})")
        if cnic:
            for v in q.filter(Vendor.cnic == cnic).limit(5):
                matches.append(_vendor_row(v))
                warnings.append(f"Vendor with CNIC {cnic} already exists ({v.code})")

    elif entity == "inventory":
        barcode = (data.get("barcode") or "").strip()
        part = (data.get("part_number") or data.get("manufacturer_part_number") or "").strip()
        exclude_id = data.get("exclude_id")
        q = db.query(Inventory)
        if exclude_id:
            q = q.filter(Inventory.id != int(exclude_id))
        if barcode:
            for i in q.filter(Inventory.barcode == barcode).limit(5):
                matches.append(_inventory_row(i))
                warnings.append(f"Item with barcode {barcode} already exists ({i.part_number})")
        if part:
            for i in q.filter(
                or_(
                    Inventory.part_number == part,
                    Inventory.manufacturer_part_number == part,
                )
            ).limit(5):
                matches.append(_inventory_row(i))
                warnings.append(f"Item with part code {part} already exists ({i.part_number})")

    elif entity == "worker":
        cnic = (data.get("cnic") or "").strip()
        phone = (data.get("phone") or "").strip()
        exclude_id = data.get("exclude_id")
        q = db.query(Worker)
        if exclude_id:
            q = q.filter(Worker.id != int(exclude_id))
        if cnic:
            for w in q.filter(Worker.cnic == cnic).limit(5):
                matches.append(_worker_row(w))
                warnings.append(f"Employee with CNIC {cnic} already exists ({w.employee_id})")
        if phone:
            for w in q.filter(Worker.phone == phone).limit(5):
                matches.append(_worker_row(w))
                warnings.append(f"Employee with phone {phone} already exists ({w.employee_id})")
    else:
        return _json({"error": f"type must be one of {ENTITY_TYPES}"}, 400)

    # de-dupe matches by id
    seen = set()
    unique = []
    for m in matches:
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        unique.append(m)

    return _json(
        {
            "duplicate": len(unique) > 0,
            "matches": unique,
            "warnings": list(dict.fromkeys(warnings)),
            "message": warnings[0] if warnings else None,
        },
        200,
    )


@router.get("/gate-passes")
def list_gate_passes(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles(
            ["admin", "accountant", "inventory_manager", "service_advisor", "technician", "manager"]
        )
    ),
):
    limit = min(int(request.query_params.get("limit", 50)), 200)
    rows = db.query(YardGatePass).order_by(YardGatePass.id.desc()).limit(limit).all()
    return _json({"gate_passes": [g.to_dict() for g in rows], "count": len(rows)}, 200)


@router.post("/gate-passes")
@idempotent_create
def create_gate_pass(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(
        require_roles(
            ["admin", "accountant", "inventory_manager", "service_advisor", "technician", "manager"]
        )
    ),
):
    data = body or {}
    direction = (data.get("direction") or "in").strip().lower()
    if direction not in ("in", "out"):
        return _json({"error": "direction must be 'in' or 'out'"}, 400)

    customer = resolve_customer(
        db, data.get("customer_id"), data.get("customer_name"), data.get("customer_phone")
    )
    car = resolve_car(
        db,
        data.get("car_id"),
        data.get("plate_no"),
        data.get("vin"),
        customer.id if customer else None,
    )
    gp = YardGatePass(
        direction=direction,
        customer_id=customer.id if customer else data.get("customer_id"),
        car_id=car.id if car else data.get("car_id"),
        visit_id=data.get("visit_id"),
        repair_order_id=data.get("repair_order_id"),
        plate_no=(car.plate_no if car else None) or data.get("plate_no"),
        customer_name=(customer.name if customer else None) or data.get("customer_name"),
        purpose=data.get("purpose"),
        notes=data.get("notes"),
        passed_at=datetime.utcnow(),
        created_by_user=current_user.username if current_user else None,
    )
    db.add(gp)
    db.commit()
    db.refresh(gp)
    return _json({"message": "Gate pass created", "gate_pass": gp.to_dict()}, 201)
