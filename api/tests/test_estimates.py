"""Estimates: advance policy math, stock gaps, revise, liability deposits."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.deposits import create_deposit
from app.estimates import (
    advance_received,
    estimate_bundle,
    required_advance,
    revise_estimate,
    stock_gaps_for_invoice,
)
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import current_branch_id, current_reason, current_user_obj
from app.foundation.hooks import install_foundation_hooks
from app.models import Attachment, Customer, Inventory, Invoice, InvoiceItem, InvoiceLabour


@pytest.fixture()
def db(tmp_path, monkeypatch):
    install_foundation_hooks()
    monkeypatch.setattr("app.log_utils.UPLOAD_FOLDER", str(tmp_path / "uploads"))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    t1 = current_branch_id.set(DEFAULT_BRANCH_ID)
    t2 = current_reason.set("estimate test")
    t3 = current_user_obj.set(SimpleNamespace(username="advisor", role="service_advisor"))
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        current_branch_id.reset(t1)
        current_reason.reset(t2)
        current_user_obj.reset(t3)


def test_required_advance_percent_of_100000_is_50000():
    assert required_advance(100_000, {"mode": "percent", "percent": 50}) == 50_000.0
    assert required_advance(100_000, {"mode": "full"}) == 100_000.0
    assert required_advance(100_000, {"mode": "none"}) == 0.0
    assert required_advance(100_000, {"mode": "fixed", "fixed_amount": 10_000}) == 10_000.0
    assert (
        required_advance(
            100_000,
            {"mode": "custom", "allow_authorized_custom": True},
            custom_amount=25_000,
            authorized=True,
        )
        == 25_000.0
    )


def test_stock_gaps_and_deposit_liability(db):
    inv = Inventory(
        name="Filter",
        part_number="FLT-1",
        category="filters",
        quantity=2,
        reserved=0,
        price=500,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(inv)
    db.flush()
    quote = Invoice(
        customer_name="Ali",
        customer_address="",
        customer_phone="0300",
        customer_reg_no="ABC",
        customer_made="Civic",
        customer_mileage="",
        balance=5000,
        advance=0,
        net_total=5000,
        discount=0,
        type_of="quote",
        include_tax=False,
        tax_amount=0,
        status="pending",
        approval_state="draft",
        required_advance=2500,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(quote)
    db.flush()
    db.add(
        InvoiceItem(
            invoice_id=quote.id,
            product_name="Filter",
            part_number="FLT-1",
            quantity=5,
            price=500,
            inventory_id=inv.id,
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.add(
        InvoiceLabour(
            invoice_id=quote.id,
            description="Fit filter",
            price=2500,
            std_hours=1,
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.commit()

    gaps = stock_gaps_for_invoice(db, quote)
    assert len(gaps) == 1
    assert gaps[0]["missing"] == 3
    assert gaps[0]["available"] == 2

    att = Attachment(
        entity_type="deposit_evidence",
        file_path="uploads/ev.png",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(att)
    db.flush()
    cust = Customer(name="Ali", phone="0300", branch_id=DEFAULT_BRANCH_ID)
    db.add(cust)
    db.flush()
    dep = create_deposit(
        db,
        amount=2500,
        visit_id=None,
        customer_id=cust.id,
        quote_invoice_id=quote.id,
        evidence_attachment_id=att.id,
        user=SimpleNamespace(username="cashier", id=1),
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.commit()
    assert dep.status == "open"
    assert advance_received(db, quote.id) == 2500.0

    bundle = estimate_bundle(db, quote.id)
    assert bundle["money"]["is_revenue"] is False
    assert bundle["money"]["advances_are_liability"] is True
    assert bundle["money"]["advance_received"] == 2500.0
    assert bundle["money"]["remaining_advance_due"] == 0.0
    assert bundle["missing_parts_count"] == 1


def test_rollup_approval_state_and_quote_advance_is_zero(db):
    from app.estimates import apply_estimate_money_fields, rollup_approval_state
    from app.foundation.settings import set_setting, SETTING_ADVANCE_POLICY

    set_setting(
        db,
        SETTING_ADVANCE_POLICY,
        {"mode": "percent", "percent": 50, "fixed_amount": 0, "allow_authorized_custom": True},
    )
    quote = Invoice(
        customer_name="Bilal",
        customer_address="",
        customer_phone="0322",
        customer_reg_no="REG1",
        customer_made="Alto",
        customer_mileage="",
        balance=100_000,
        advance=999,  # should be forced to 0 for estimates
        net_total=100_000,
        discount=0,
        type_of="quote",
        include_tax=False,
        tax_amount=0,
        status="pending",
        approval_state="sent",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(quote)
    db.flush()
    db.add(
        InvoiceItem(
            invoice_id=quote.id,
            product_name="Pad",
            quantity=1,
            price=40_000,
            approval_status="approved",
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.add(
        InvoiceLabour(
            invoice_id=quote.id,
            description="Labour",
            price=60_000,
            approval_status="approved",
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.flush()
    assert rollup_approval_state(quote) == "approved"
    apply_estimate_money_fields(db, quote)
    quote.advance = 0.0
    assert float(quote.required_advance or 0) == 50_000.0
    assert float(quote.advance or 0) == 0.0


def test_labour_code_entity_search(db):
    from app.models import LabourCode
    from app.routers import entities as entities_router

    db.add(
        LabourCode(
            code="LB-AC",
            description="AC diagnosis",
            standard_hours=1.5,
            rate=3500,
            category="ac",
            is_active=True,
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.commit()
    rows = entities_router._search_labour_codes(db, "AC", 10)
    assert len(rows) == 1
    assert rows[0]["code"] == "LB-AC"
    assert rows[0]["entity_type"] == "labour_code"
    assert rows[0]["rate"] == 3500


def test_revise_preserves_parent_and_marks_revised(db):
    quote = Invoice(
        customer_name="Sara",
        customer_address="",
        customer_phone="0311",
        customer_reg_no="XYZ",
        customer_made="City",
        customer_mileage="",
        balance=1000,
        advance=0,
        net_total=1000,
        discount=0,
        type_of="quote",
        include_tax=False,
        tax_amount=0,
        status="pending",
        approval_state="sent",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(quote)
    db.flush()
    db.add(
        InvoiceLabour(
            invoice_id=quote.id,
            description="Diagnose",
            price=1000,
            approval_status="pending",
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.commit()
    user = SimpleNamespace(username="advisor")
    clone = revise_estimate(db, quote, user)
    db.commit()
    assert clone.parent_quote_id == quote.id
    assert clone.approval_state == "draft"
    assert quote.approval_state == "revised"
    assert clone.id != quote.id
