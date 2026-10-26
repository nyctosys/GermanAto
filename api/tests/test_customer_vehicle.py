"""Customer / vehicle management: phone lookup, reuse, no duplicate on link."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.customer_vehicle import (
    find_customers_by_phone,
    find_existing_car,
    load_customer_bundle,
)
from app.db import Base
from app.document_links import apply_links, resolve_customer
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import current_branch_id, current_reason, current_user_obj
from app.foundation.hooks import install_foundation_hooks
from app.models import Car, Customer, Invoice, RepairOrder


@pytest.fixture()
def db(tmp_path, monkeypatch):
    install_foundation_hooks()
    monkeypatch.setattr("app.log_utils.UPLOAD_FOLDER", str(tmp_path / "uploads"))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    t1 = current_branch_id.set(DEFAULT_BRANCH_ID)
    t2 = current_reason.set("customer test")
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


def test_phone_lookup_finds_customer(db: Session):
    c = Customer(
        name="Ali",
        phone="+923001112233",
        address="Lahore",
        customer_type="retail",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(c)
    db.commit()
    hits = find_customers_by_phone(db, "03001112233")
    assert len(hits) == 1
    assert hits[0].id == c.id


def test_reuse_car_by_plate_and_owner(db: Session):
    c = Customer(name="Sara", phone="+923004445566", branch_id=DEFAULT_BRANCH_ID)
    db.add(c)
    db.flush()
    car = Car(
        make="Honda",
        model="Civic",
        plate_no="ABC-123",
        customer_id=c.id,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(car)
    db.commit()
    found = find_existing_car(db, plate_no="abc-123", customer_id=c.id)
    assert found is not None
    assert found.id == car.id


def test_job_card_links_existing_customer_without_duplicate(db: Session):
    c = Customer(name="Owner", phone="+923007778899", branch_id=DEFAULT_BRANCH_ID)
    db.add(c)
    db.flush()
    car = Car(
        make="Toyota",
        model="Corolla",
        plate_no="LEB-999",
        customer_id=c.id,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(car)
    db.commit()

    ro = RepairOrder(
        customer_name="Owner",
        customer_phone="+923007778899",
        customer_address="x",
        customer_reg_no="LEB-999",
        customer_made="Toyota Corolla",
        customer_mileage="10",
        current_status="received",
        branch_id=DEFAULT_BRANCH_ID,
    )
    apply_links(
        db,
        ro,
        {
            "customer_id": c.id,
            "customer_name": "Owner",
            "customer_phone": "+923007778899",
            "car_id": car.id,
            "customer_reg_no": "LEB-999",
        },
    )
    assert ro.customer_id == c.id
    assert ro.car_id == car.id
    assert db.query(Customer).count() == 1
    assert db.query(Car).count() == 1


def test_customer_bundle_includes_balance(db: Session):
    c = Customer(name="Bal", phone="+923001234567", branch_id=DEFAULT_BRANCH_ID)
    db.add(c)
    db.flush()
    inv = Invoice(
        customer_name="Bal",
        customer_address="x",
        customer_phone="+923001234567",
        customer_reg_no="X",
        customer_made="Y",
        customer_mileage="1",
        balance=500,
        advance=0,
        net_total=500,
        discount=0,
        type_of="invoice",
        include_tax=False,
        tax_amount=0,
        paid_amount=0,
        status="unpaid",
        customer_id=c.id,
        created_at=datetime.utcnow(),
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(inv)
    db.commit()
    bundle = load_customer_bundle(db, c.id)
    assert bundle is not None
    assert bundle["activity"]["receivable_total"] == 500
    assert bundle["activity"]["counts"]["invoices"] == 1


def test_resolve_customer_by_normalized_phone(db: Session):
    c = Customer(name="Norm", phone="+923009998887", branch_id=DEFAULT_BRANCH_ID)
    db.add(c)
    db.commit()
    found = resolve_customer(db, None, "Norm", "03009998887")
    assert found is not None
    assert found.id == c.id
