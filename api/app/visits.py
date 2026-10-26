"""Visit / check-in inspection: templates, create visit, gate job cards."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.foundation.audit import audit_write
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import get_branch
from app.foundation.settings import comeback_window_days
from app.log_utils import save_data_url
from app.models import (
    Attachment,
    Car,
    Customer,
    InspectionTemplate,
    RepairOrder,
    Visit,
    VisitInspectionItem,
)

DEFAULT_INSPECTION_POINTS: list[dict[str, Any]] = [
    {"key": "ext_front", "label": "Front bumper / grille", "category": "exterior", "requires_photo": False, "sort_order": 10},
    {"key": "ext_rear", "label": "Rear bumper / trunk", "category": "exterior", "requires_photo": False, "sort_order": 20},
    {"key": "ext_left", "label": "Left side panels", "category": "exterior", "requires_photo": False, "sort_order": 30},
    {"key": "ext_right", "label": "Right side panels", "category": "exterior", "requires_photo": False, "sort_order": 40},
    {"key": "lights_head", "label": "Headlights", "category": "lights", "requires_photo": False, "sort_order": 50},
    {"key": "lights_tail", "label": "Tail lights", "category": "lights", "requires_photo": False, "sort_order": 60},
    {"key": "lights_indicators", "label": "Indicators", "category": "lights", "requires_photo": False, "sort_order": 70},
    {"key": "tyre_fl", "label": "Front left tyre", "category": "tyres", "requires_photo": False, "sort_order": 80},
    {"key": "tyre_fr", "label": "Front right tyre", "category": "tyres", "requires_photo": False, "sort_order": 90},
    {"key": "tyre_rl", "label": "Rear left tyre", "category": "tyres", "requires_photo": False, "sort_order": 100},
    {"key": "tyre_rr", "label": "Rear right tyre", "category": "tyres", "requires_photo": False, "sort_order": 110},
    {"key": "int_seats", "label": "Seats / upholstery", "category": "interior", "requires_photo": False, "sort_order": 120},
    {"key": "int_dash", "label": "Dashboard / controls", "category": "interior", "requires_photo": False, "sort_order": 130},
    {"key": "fluid_oil", "label": "Engine oil level", "category": "fluids", "requires_photo": False, "sort_order": 140},
    {"key": "fluid_coolant", "label": "Coolant", "category": "fluids", "requires_photo": False, "sort_order": 150},
    {"key": "acc_keys", "label": "Keys left with workshop", "category": "accessories", "requires_photo": False, "sort_order": 160},
    {"key": "acc_docs", "label": "Documents left", "category": "accessories", "requires_photo": False, "sort_order": 170},
]

_VALID_RESULTS = frozenset({"ok", "issue", "na"})


def ensure_default_inspection_template(db: Session) -> InspectionTemplate:
    row = (
        db.query(InspectionTemplate)
        .filter(InspectionTemplate.is_default.is_(True), InspectionTemplate.deleted_at.is_(None))
        .first()
    )
    if row:
        return row
    row = InspectionTemplate(
        name="Default check-in",
        is_default=True,
        is_active=True,
        points_json=json.dumps(DEFAULT_INSPECTION_POINTS),
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(row)
    db.flush()
    return row


def get_active_template(db: Session) -> InspectionTemplate:
    tpl = ensure_default_inspection_template(db)
    if not tpl.is_active:
        raise HTTPException(status_code=400, detail="Inspection template is inactive")
    return tpl


def _attach_data_url(
    db: Session,
    data_url: str | None,
    *,
    entity_type: str,
    entity_id: int | None,
    branch_id: str,
    uploaded_by: str | None,
    notes: str,
    prefix: str,
) -> Attachment | None:
    path = save_data_url(data_url, prefix=prefix)
    if not path:
        return None
    row = Attachment(
        branch_id=branch_id,
        entity_type=entity_type,
        entity_id=entity_id,
        file_path=path,
        original_name=f"{prefix}.png",
        content_type="image/png",
        uploaded_by=uploaded_by,
        notes=notes,
    )
    db.add(row)
    db.flush()
    return row


def _detect_comeback(db: Session, car_id: int, when: datetime) -> bool:
    window = comeback_window_days(db)
    if window <= 0:
        return False
    cutoff = when - timedelta(days=window)
    prior = (
        db.query(RepairOrder)
        .filter(
            RepairOrder.car_id == car_id,
            RepairOrder.created_at.isnot(None),
            RepairOrder.created_at >= cutoff,
            RepairOrder.created_at < when,
        )
        .order_by(RepairOrder.created_at.desc())
        .first()
    )
    return prior is not None


def create_visit(
    db: Session,
    *,
    car: Car,
    data: dict,
    user,
    branch_id: str | None = None,
) -> Visit:
    """Create a completed check-in visit. Signature + all template points required."""
    bid = branch_id or get_branch() or DEFAULT_BRANCH_ID
    by = getattr(user, "username", None) if user else None
    tpl = get_active_template(db)
    points = tpl.points() or DEFAULT_INSPECTION_POINTS
    if not points:
        raise HTTPException(status_code=400, detail="Inspection template has no points")

    signature_url = data.get("signature_data_url") or data.get("signature")
    if not signature_url:
        raise HTTPException(
            status_code=400,
            detail={"error": "Customer signature is required", "require_signature": True},
        )

    items_in = data.get("items") or []
    if not isinstance(items_in, list):
        raise HTTPException(status_code=400, detail="items must be a list")
    by_key = {str(i.get("key") or i.get("point_key") or ""): i for i in items_in if isinstance(i, dict)}

    missing = [p["key"] for p in points if p["key"] not in by_key]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Inspection checklist incomplete",
                "require_inspection": True,
                "missing_points": missing,
            },
        )

    for p in points:
        item = by_key[p["key"]]
        result = str(item.get("result") or "").strip().lower()
        if result not in _VALID_RESULTS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid result for {p['key']} (use ok/issue/na)",
            )
        if p.get("requires_photo") and result == "issue" and not item.get("photo_data_url") and not item.get("photo"):
            raise HTTPException(
                status_code=400,
                detail=f"Photo required for issue on {p['label']}",
            )

    customer_id = data.get("customer_id", car.customer_id)
    if customer_id is not None:
        cust = db.get(Customer, int(customer_id))
        if cust is None or getattr(cust, "deleted_at", None) is not None:
            raise HTTPException(status_code=400, detail="Customer not found or deleted")
        customer_id = cust.id

    now = datetime.utcnow()
    visit = Visit(
        car_id=car.id,
        customer_id=customer_id,
        odometer=str(data.get("odometer") or car.mileage or "").strip() or None,
        fuel_level=str(data.get("fuel_level") or "").strip() or None,
        reported_complaints=(data.get("reported_complaints") or "").strip() or None,
        existing_damage=(data.get("existing_damage") or "").strip() or None,
        template_id=tpl.id,
        status="completed",
        is_comeback=_detect_comeback(db, car.id, now),
        checked_in_by=by,
        check_in_at=now,
        branch_id=bid,
    )
    db.add(visit)
    db.flush()

    sig = _attach_data_url(
        db,
        signature_url,
        entity_type="visit_signature",
        entity_id=visit.id,
        branch_id=bid,
        uploaded_by=by,
        notes=f"Check-in signature visit {visit.id}",
        prefix="signature",
    )
    if not sig:
        raise HTTPException(
            status_code=400,
            detail={"error": "Customer signature is required", "require_signature": True},
        )
    visit.signature_attachment_id = sig.id

    ordered = sorted(points, key=lambda x: int(x.get("sort_order") or 0))
    for idx, p in enumerate(ordered):
        raw = by_key[p["key"]]
        result = str(raw.get("result") or "ok").strip().lower()
        photo = None
        photo_url = raw.get("photo_data_url") or raw.get("photo")
        if photo_url:
            photo = _attach_data_url(
                db,
                photo_url,
                entity_type="visit_inspection_photo",
                entity_id=visit.id,
                branch_id=bid,
                uploaded_by=by,
                notes=f"{p['key']} on visit {visit.id}",
                prefix=p["key"],
            )
        db.add(
            VisitInspectionItem(
                visit_id=visit.id,
                point_key=p["key"],
                label=p.get("label") or p["key"],
                category=p.get("category") or "general",
                result=result,
                notes=(raw.get("notes") or "").strip() or None,
                photo_attachment_id=photo.id if photo else None,
                sort_order=int(p.get("sort_order") or (idx + 1) * 10),
                branch_id=bid,
            )
        )

    if visit.odometer:
        car.mileage = visit.odometer

    audit_write(
        db,
        user=user,
        action="CHECK_IN",
        module="visit",
        reference_id=visit.id,
        details=f"Check-in visit for car {car.id}" + (" (comeback)" if visit.is_comeback else ""),
        new_value=visit.to_dict(include_items=False),
        reason=(data.get("reason") or "Vehicle check-in").strip(),
        branch_id=bid,
    )
    db.flush()
    return visit


def visit_is_complete(visit: Visit) -> bool:
    if not visit.signature_attachment_id:
        return False
    if not visit.items:
        return False
    return all((i.result or "").lower() in _VALID_RESULTS for i in visit.items)


def _load_visit_for_car(db: Session, *, car_id: int, visit_id: int) -> Visit:
    visit = (
        db.query(Visit)
        .options(joinedload(Visit.items), joinedload(Visit.signature))
        .filter(Visit.id == int(visit_id), Visit.car_id == int(car_id))
        .first()
    )
    if visit is None or getattr(visit, "deleted_at", None) is not None:
        raise HTTPException(status_code=400, detail="Visit not found for this car")
    if not visit_is_complete(visit):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Visit must include customer signature and a full inspection checklist",
                "require_signature": not bool(visit.signature_attachment_id),
                "require_inspection": True,
            },
        )
    return visit


def require_visit_for_job_card(
    db: Session,
    *,
    car_id: int | None,
    visit_id: int | None,
    for_repair_order: bool = True,
) -> Visit | None:
    """When a car is linked, a completed signed inspection visit is required.

    Returns the visit (and RO caller should set repair_order_id). Returns None only
    when car_id is absent (legacy walk-in without car record).

    for_repair_order=True also rejects visits already linked to an RO.
    Job cards use for_repair_order=False (visit may later open an RO).
    """
    if not car_id:
        return None
    if not visit_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Completed check-in inspection with customer signature is required before creating a job card",
                "require_visit": True,
            },
        )
    visit = _load_visit_for_car(db, car_id=int(car_id), visit_id=int(visit_id))
    if for_repair_order and visit.repair_order_id:
        raise HTTPException(
            status_code=400,
            detail="This check-in visit is already linked to a repair order",
        )
    return visit


def get_visit(db: Session, visit_id: int) -> Visit:
    visit = (
        db.query(Visit)
        .options(
            joinedload(Visit.items).joinedload(VisitInspectionItem.photo),
            joinedload(Visit.signature),
            joinedload(Visit.customer),
            joinedload(Visit.car),
        )
        .filter(Visit.id == visit_id)
        .first()
    )
    if visit is None or getattr(visit, "deleted_at", None) is not None:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


def update_visit(db: Session, visit_id: int, data: dict, user) -> Visit:
    """Update intake inspection notes / odometer / fuel / checklist items."""
    visit = get_visit(db, visit_id)
    old = visit.to_dict()

    for f in ("odometer", "fuel_level", "reported_complaints", "existing_damage", "status"):
        if f in data and data[f] is not None:
            setattr(visit, f, str(data[f]).strip() if not isinstance(data[f], str) else data[f].strip())

    items_raw = data.get("items")
    if items_raw is not None:
        by_key = {it.point_key: it for it in (visit.items or [])}
        for raw in items_raw:
            key = str(raw.get("point_key") or "").strip()
            if not key or key not in by_key:
                continue
            item = by_key[key]
            if "result" in raw and raw["result"] is not None:
                result = str(raw["result"]).strip().lower()
                if result not in _VALID_RESULTS:
                    raise HTTPException(status_code=400, detail=f"Invalid result for {key}")
                item.result = result
            if "notes" in raw:
                item.notes = str(raw.get("notes") or "").strip() or None
            photo_url = raw.get("photo_data_url") or raw.get("photo")
            if photo_url:
                bid = visit.branch_id or get_branch() or DEFAULT_BRANCH_ID
                att = _attach_data_url(
                    db,
                    photo_url,
                    entity_type="visit_inspection_photo",
                    entity_id=visit.id,
                    branch_id=bid,
                    uploaded_by=getattr(user, "username", None),
                    notes=f"{key} update on visit {visit.id}",
                    prefix=key,
                )
                if att:
                    item.photo_attachment_id = att.id

    db.flush()
    audit_write(
        db,
        user=user,
        action="UPDATE",
        module="visits",
        reference_id=visit.id,
        details=f"Updated visit inspection #{visit.id}",
        old_value=old,
        new_value=visit.to_dict(),
        reason=data.get("reason"),
    )
    return get_visit(db, visit_id)
