"""Check-in visit rules: signature/inspection required; job-card gate; history visits."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.car_ownership import build_car_history
from app.db import Base
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import current_branch_id, current_reason, current_user_obj
from app.foundation.hooks import install_foundation_hooks
from app.models import Car, Customer, RepairOrder
from app.visits import (
    DEFAULT_INSPECTION_POINTS,
    create_visit,
    ensure_default_inspection_template,
    require_visit_for_job_card,
)

# 1x1 PNG
_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    install_foundation_hooks()
    monkeypatch.setattr("app.log_utils.UPLOAD_FOLDER", str(tmp_path / "uploads"))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    t1 = current_branch_id.set(DEFAULT_BRANCH_ID)
    t2 = current_reason.set("check-in test")
    t3 = current_user_obj.set(None)
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        current_branch_id.reset(t1)
        current_reason.reset(t2)
        current_user_obj.reset(t3)
        engine.dispose()


def _seed(db: Session):
    ensure_default_inspection_template(db)
    c = Customer(name="Owner", phone="+923001111111", branch_id=DEFAULT_BRANCH_ID)
    db.add(c)
    db.flush()
    car = Car(
        make="Honda",
        model="Civic",
        plate_no="XYZ-999",
        vin="1HGBH41JXMN109186",
        mileage="10000",
        customer_id=c.id,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(car)
    db.commit()
    db.refresh(car)
    return c, car


def _items(result: str = "ok"):
    return [{"key": p["key"], "result": result, "notes": ""} for p in DEFAULT_INSPECTION_POINTS]


def test_visit_requires_signature(db: Session):
    _, car = _seed(db)
    with pytest.raises(HTTPException) as ei:
        create_visit(
            db,
            car=car,
            data={"odometer": "10001", "items": _items()},
            user=SimpleNamespace(username="sa"),
        )
    assert ei.value.status_code == 400
    assert ei.value.detail.get("require_signature") is True


def test_visit_requires_full_checklist(db: Session):
    _, car = _seed(db)
    with pytest.raises(HTTPException) as ei:
        create_visit(
            db,
            car=car,
            data={
                "odometer": "10001",
                "signature_data_url": _PNG,
                "items": [{"key": "ext_front", "result": "ok"}],
            },
            user=SimpleNamespace(username="sa"),
        )
    assert ei.value.status_code == 400
    assert ei.value.detail.get("require_inspection") is True


def test_create_visit_and_history_includes_visit(db: Session):
    _, car = _seed(db)
    visit = create_visit(
        db,
        car=car,
        data={
            "odometer": "10050",
            "fuel_level": "half",
            "reported_complaints": "Noise",
            "signature_data_url": _PNG,
            "items": _items(),
        },
        user=SimpleNamespace(username="sa"),
    )
    db.commit()
    assert visit.signature_attachment_id
    assert len(visit.items) == len(DEFAULT_INSPECTION_POINTS)

    hist = build_car_history(db, car.id, kinds={"visit"})
    assert hist["count"] >= 1
    assert any(e["kind"] == "visit" for e in hist["events"])


def test_job_card_requires_visit_when_car_linked(db: Session):
    _, car = _seed(db)
    with pytest.raises(HTTPException) as ei:
        require_visit_for_job_card(db, car_id=car.id, visit_id=None)
    assert ei.value.detail.get("require_visit") is True

    visit = create_visit(
        db,
        car=car,
        data={"odometer": "10100", "signature_data_url": _PNG, "items": _items()},
        user=SimpleNamespace(username="sa"),
    )
    db.commit()
    linked = require_visit_for_job_card(db, car_id=car.id, visit_id=visit.id)
    assert linked.id == visit.id

    # Walk-in without car is allowed
    assert require_visit_for_job_card(db, car_id=None, visit_id=None) is None


def test_timeline_orders_visits_with_ros(db: Session):
    _, car = _seed(db)
    ro = RepairOrder(
        customer_name="Owner",
        customer_phone="+923001111111",
        customer_address="",
        customer_reg_no=car.plate_no or "",
        customer_made="Honda Civic",
        customer_mileage="9000",
        car_id=car.id,
        current_status="received",
        branch_id=DEFAULT_BRANCH_ID,
        created_at=datetime(2024, 1, 1, 10, 0, 0),
    )
    db.add(ro)
    db.flush()
    visit = create_visit(
        db,
        car=car,
        data={"odometer": "11000", "signature_data_url": _PNG, "items": _items()},
        user=SimpleNamespace(username="sa"),
    )
    visit.check_in_at = datetime(2024, 6, 1, 12, 0, 0)
    db.commit()

    hist = build_car_history(db, car.id)
    kinds = [e["kind"] for e in hist["events"]]
    assert "visit" in kinds
    assert "repair_order" in kinds
    # Newest first
    assert hist["events"][0]["at"] >= hist["events"][-1]["at"]
