"""Car transfer rules + unified history timeline ordering (SQLite in-memory)."""

from __future__ import annotations

import io
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.car_ownership import build_car_history, transfer_car_ownership
from app.db import Base
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import current_branch_id, current_reason, current_user_obj
from app.foundation.hooks import install_foundation_hooks
from app.models import Car, Customer, Invoice, RepairOrder, RepairOrderPart


class FakeUpload:
    def __init__(self, name: str = "proof.pdf", content: bytes = b"%PDF-1.4 fake"):
        self.filename = name
        self.content_type = "application/pdf"
        self.file = io.BytesIO(content)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    install_foundation_hooks()
    # Keep uploads inside pytest tmp
    monkeypatch.setattr(
        "app.log_utils.UPLOAD_FOLDER",
        str(tmp_path / "uploads"),
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    t1 = current_branch_id.set(DEFAULT_BRANCH_ID)
    t2 = current_reason.set("test transfer")
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


def _seed_customers_and_car(db: Session):
    a = Customer(name="Alice", phone="+923001111111", address="A", branch_id=DEFAULT_BRANCH_ID)
    b = Customer(name="Bob", phone="+923002222222", address="B", branch_id=DEFAULT_BRANCH_ID)
    db.add_all([a, b])
    db.flush()
    car = Car(
        make="Toyota",
        model="Corolla",
        plate_no="ABC-123",
        vin="JTDBR32E720000001",
        mileage="50000",
        customer_id=a.id,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(car)
    db.commit()
    db.refresh(a)
    db.refresh(b)
    db.refresh(car)
    return a, b, car


def test_transfer_updates_owner_keeps_invoice_customer(db: Session):
    a, b, car = _seed_customers_and_car(db)
    inv = Invoice(
        customer_name=a.name,
        customer_address=a.address or "",
        customer_phone=a.phone or "",
        customer_reg_no=car.plate_no or "",
        customer_made=f"{car.make} {car.model}",
        customer_mileage="50000",
        customer_id=a.id,
        car_id=car.id,
        balance=1000.0,
        advance=0.0,
        net_total=1000.0,
        discount=0.0,
        type_of="invoice",
        status="pending",
        branch_id=DEFAULT_BRANCH_ID,
        created_at=datetime(2024, 1, 10, 12, 0, 0),
    )
    db.add(inv)
    db.commit()

    user = SimpleNamespace(username="advisor1")
    ownership = transfer_car_ownership(
        db,
        car=car,
        to_customer_id=b.id,
        transfer_date=date(2024, 6, 1),
        reason="Sold to Bob",
        evidence_file=FakeUpload(),
        user=user,
    )
    db.commit()

    assert ownership.from_customer_id == a.id
    assert ownership.to_customer_id == b.id
    assert ownership.evidence_attachment_id
    assert car.customer_id == b.id

    db.refresh(inv)
    assert inv.customer_id == a.id
    assert inv.car_id == car.id


def test_transfer_rejects_same_owner(db: Session):
    a, _b, car = _seed_customers_and_car(db)
    with pytest.raises(HTTPException) as exc:
        transfer_car_ownership(
            db,
            car=car,
            to_customer_id=a.id,
            transfer_date=date.today(),
            reason="noop",
            evidence_file=FakeUpload(),
            user=SimpleNamespace(username="u"),
        )
    assert exc.value.status_code == 400
    assert "same owner" in str(exc.value.detail).lower()


def test_transfer_rejects_missing_customer(db: Session):
    _a, _b, car = _seed_customers_and_car(db)
    with pytest.raises(HTTPException) as exc:
        transfer_car_ownership(
            db,
            car=car,
            to_customer_id=99999,
            transfer_date=date.today(),
            reason="ghost",
            evidence_file=FakeUpload(),
            user=SimpleNamespace(username="u"),
        )
    assert exc.value.status_code == 404


def test_transfer_rejects_deleted_customer(db: Session):
    a, b, car = _seed_customers_and_car(db)
    b.deleted_at = datetime.utcnow()
    db.commit()
    with pytest.raises(HTTPException) as exc:
        transfer_car_ownership(
            db,
            car=car,
            to_customer_id=b.id,
            transfer_date=date.today(),
            reason="to deleted",
            evidence_file=FakeUpload(),
            user=SimpleNamespace(username="u"),
        )
    assert exc.value.status_code == 404
    assert car.customer_id == a.id


def test_transfer_requires_evidence(db: Session):
    _a, b, car = _seed_customers_and_car(db)
    with pytest.raises(HTTPException) as exc:
        transfer_car_ownership(
            db,
            car=car,
            to_customer_id=b.id,
            transfer_date=date.today(),
            reason="no file",
            evidence_file=None,
            user=SimpleNamespace(username="u"),
        )
    assert exc.value.status_code == 400
    assert "evidence" in str(exc.value.detail).lower()


def test_history_timeline_newest_first(db: Session):
    a, b, car = _seed_customers_and_car(db)

    inv = Invoice(
        customer_name=a.name,
        customer_address="",
        customer_phone=a.phone or "",
        customer_reg_no=car.plate_no or "",
        customer_made="Toyota Corolla",
        customer_mileage="51000",
        customer_id=a.id,
        car_id=car.id,
        balance=500.0,
        advance=0.0,
        net_total=500.0,
        discount=0.0,
        type_of="quote",
        status="pending",
        branch_id=DEFAULT_BRANCH_ID,
        created_at=datetime(2024, 2, 1, 10, 0, 0),
    )
    ro = RepairOrder(
        customer_name=a.name,
        customer_phone=a.phone or "",
        customer_address="",
        customer_reg_no=car.plate_no or "",
        customer_made="Toyota Corolla",
        customer_mileage="52000",
        customer_id=a.id,
        car_id=car.id,
        current_status="in_progress",
        worker_name="Tech Ali",
        branch_id=DEFAULT_BRANCH_ID,
        created_at=datetime(2024, 3, 15, 9, 0, 0),
    )
    db.add_all([inv, ro])
    db.flush()
    db.add(
        RepairOrderPart(
            repair_order_id=ro.id,
            description="Oil filter",
            part_number="OF-1",
            quantity=1,
            status="issued",
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.commit()

    transfer_car_ownership(
        db,
        car=car,
        to_customer_id=b.id,
        transfer_date=date(2024, 5, 20),
        reason="Fleet move",
        evidence_file=FakeUpload(),
        user=SimpleNamespace(username="mgr"),
    )
    db.commit()

    payload = build_car_history(db, car.id)
    assert payload["count"] >= 3
    ats = [e["at"] for e in payload["events"] if e["at"]]
    assert ats == sorted(ats, reverse=True)

    kinds = {e["kind"] for e in payload["events"]}
    assert "ownership" in kinds
    assert "quote" in kinds
    assert "repair_order" in kinds
    assert "parts" in kinds

    ownership_only = build_car_history(db, car.id, kinds={"ownership"})
    assert ownership_only["count"] >= 1
    assert all(e["kind"] == "ownership" for e in ownership_only["events"])
