"""Job card / vehicle intake: draft, document_no, search, assign, RO rename."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.document_numbers import job_card_document_no
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import current_branch_id, current_reason, current_user_obj
from app.foundation.hooks import install_foundation_hooks
from app.job_cards import create_job_card, list_job_cards, update_job_card
from app.models import (
    Attachment,
    Car,
    Customer,
    JobCard,
    RepairOrder,
    Visit,
    VisitInspectionItem,
    Worker,
)
from app.pipeline import assert_quote_from_job_card


@pytest.fixture()
def db(tmp_path, monkeypatch):
    install_foundation_hooks()
    monkeypatch.setattr("app.log_utils.UPLOAD_FOLDER", str(tmp_path / "uploads"))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    t1 = current_branch_id.set(DEFAULT_BRANCH_ID)
    t2 = current_reason.set("intake test")
    t3 = current_user_obj.set(SimpleNamespace(username="advisor", role="service_advisor"))
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        current_branch_id.reset(t1)
        current_reason.reset(t2)
        current_user_obj.reset(t3)


def _seed_customer_car_visit(db):
    c = Customer(name="Intake Cust", phone="+923001110000", branch_id=DEFAULT_BRANCH_ID)
    db.add(c)
    db.flush()
    car = Car(
        make="Toyota",
        model="Corolla",
        plate_no="INT-100",
        customer_id=c.id,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(car)
    db.flush()
    sig = Attachment(
        entity_type="visit_signature",
        file_path="uploads/sig.png",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(sig)
    db.flush()
    visit = Visit(
        car_id=car.id,
        customer_id=c.id,
        signature_attachment_id=sig.id,
        status="completed",
        odometer="55000",
        fuel_level="1/2",
        reported_complaints="AC not cooling",
        existing_damage="Scratches on bumper",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(visit)
    db.flush()
    db.add(
        VisitInspectionItem(
            visit_id=visit.id,
            point_key="ext_front",
            label="Front",
            category="exterior",
            result="ok",
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.commit()
    return c, car, visit


def test_draft_skips_visit_gate_and_gets_document_no(db):
    c, car, _visit = _seed_customer_car_visit(db)
    user = SimpleNamespace(username="advisor")
    card = create_job_card(
        db,
        {
            "customer_id": c.id,
            "car_id": car.id,
            "customer_name": c.name,
            "customer_phone": c.phone,
            "customer_reg_no": car.plate_no,
            "status": "draft",
            "priority": "high",
            "problem_description": "Noise",
            "lines": [],
        },
        user,
    )
    db.commit()
    assert card.status == "draft"
    assert card.document_no == job_card_document_no(card.id)
    assert card.priority == "high"
    with pytest.raises(Exception):
        assert_quote_from_job_card(card)


def test_open_job_card_prefills_from_visit_and_searchable(db):
    c, car, visit = _seed_customer_car_visit(db)
    user = SimpleNamespace(username="advisor")
    card = create_job_card(
        db,
        {
            "customer_id": c.id,
            "car_id": car.id,
            "visit_id": visit.id,
            "customer_name": c.name,
            "customer_phone": c.phone,
            "customer_reg_no": car.plate_no,
            "status": "open",
            "priority": "urgent",
            "lines": [],
        },
        user,
    )
    db.commit()
    assert card.odometer == "55000"
    assert card.fuel_level == "1/2"
    assert card.problem_description == "AC not cooling"
    assert card.inspection_notes == "Scratches on bumper"
    rows = list_job_cards(db, q="INT-100")
    assert any(r.id == card.id for r in rows)
    rows2 = list_job_cards(db, q=card.document_no)
    assert any(r.id == card.id for r in rows2)


def test_quote_from_job_card_zeros_advance_and_sets_required(db):
    from app.foundation.settings import SETTING_ADVANCE_POLICY, set_setting
    from app.job_cards import build_quote_from_job_card, create_job_card

    set_setting(
        db,
        SETTING_ADVANCE_POLICY,
        {"mode": "percent", "percent": 50, "fixed_amount": 0, "allow_authorized_custom": True},
    )
    c, car, visit = _seed_customer_car_visit(db)
    user = SimpleNamespace(username="advisor", id=1)
    card = create_job_card(
        db,
        {
            "customer_id": c.id,
            "car_id": car.id,
            "visit_id": visit.id,
            "customer_name": c.name,
            "status": "open",
            "lines": [
                {
                    "line_type": "labour",
                    "description": "Diagnostics",
                    "quantity": 1,
                    "unit_price": 100_000,
                    "std_hours": 2,
                    "pay_type": "customer",
                    "line_status": "Pending",
                }
            ],
        },
        user,
    )
    db.flush()
    quote = build_quote_from_job_card(
        db,
        card,
        {"include_tax": False, "discount": 0, "advance": 9999},
        user,
    )
    db.commit()
    assert (quote.type_of or "").lower() == "quote"
    assert float(quote.advance or 0) == 0.0
    assert float(quote.required_advance or 0) == 50_000.0
    assert (quote.approval_state or "") == "draft"
    assert quote.job_card_id == card.id
    assert quote.customer_id == c.id
    assert quote.car_id == car.id


def test_assign_worker_and_ro_rename_preserves_document_no(db):
    c, car, visit = _seed_customer_car_visit(db)
    from datetime import date

    w = Worker(
        first_name="Ali",
        last_name="Khan",
        employee_id="EMP-9",
        phone="03001112233",
        address="Shop",
        cnic="35202-1111111-1",
        date_of_birth=date(1990, 1, 1),
        hire_date=date(2020, 1, 1),
        position="Technician",
        department="Workshop",
        status="active",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(w)
    db.flush()
    user = SimpleNamespace(username="manager")
    card = create_job_card(
        db,
        {
            "customer_id": c.id,
            "car_id": car.id,
            "visit_id": visit.id,
            "customer_name": c.name,
            "status": "open",
            "lines": [],
        },
        user,
    )
    update_job_card(db, card, {"worker_id": w.id, "team_name": "Bay 2"}, user)
    db.commit()
    assert card.worker_id == w.id
    assert card.team_name == "Bay 2"

    ro = RepairOrder(
        customer_name=c.name,
        customer_phone=c.phone or "",
        customer_address="",
        customer_reg_no=car.plate_no or "",
        customer_made="Toyota Corolla",
        customer_mileage="55000",
        customer_id=c.id,
        car_id=car.id,
        visit_id=visit.id,
        job_card_id=card.id,
        document_no="RO-00042",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(ro)
    db.commit()
    original = ro.document_no
    ro.display_title = "Corolla AC — Ali"
    db.commit()
    assert ro.document_no == original
    assert ro.display_title == "Corolla AC — Ali"
    assert db.query(JobCard).count() == 1
