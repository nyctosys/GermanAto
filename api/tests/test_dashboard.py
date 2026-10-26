"""Dashboard aggregates from live rows — no fabricated stats."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.dashboard import build_dashboard, resolve_date_range
from app.db import Base
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import current_branch_id, current_reason, current_user_obj
from app.foundation.hooks import install_foundation_hooks
from app.models import CashReceived, Expense, Invoice, RepairOrder, Worker


class _U:
    def __init__(self, role="admin", username="admin"):
        self.role = role
        self.username = username


@pytest.fixture()
def db(tmp_path, monkeypatch):
    install_foundation_hooks()
    monkeypatch.setattr("app.log_utils.UPLOAD_FOLDER", str(tmp_path / "uploads"))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    t1 = current_branch_id.set(DEFAULT_BRANCH_ID)
    t2 = current_reason.set("dashboard test")
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


def test_resolve_date_range_month():
    start, end, period = resolve_date_range("month", None, None)
    assert period == "month"
    assert start.day == 1
    assert end == date.today()


def test_dashboard_separates_revenue_from_cash(db: Session):
    today = date.today()
    db.add(
        Invoice(
            customer_name="A",
            customer_address="x",
            customer_phone="1",
            customer_reg_no="ABC",
            customer_made="Toyota",
            customer_mileage="1",
            balance=1000,
            advance=0,
            net_total=1000,
            discount=0,
            type_of="invoice",
            include_tax=False,
            tax_amount=0,
            paid_amount=0,
            status="unpaid",
            created_at=datetime.combine(today, datetime.min.time()),
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.add(
        CashReceived(
            date=today,
            description="Walk-in",
            amount=250,
            payment_method="cash",
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.add(
        Expense(
            date=today,
            category="Fuel",
            description="Petrol",
            amount=50,
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.add(
        RepairOrder(
            customer_name="A",
            customer_phone="1",
            customer_address="x",
            customer_reg_no="ABC-123",
            customer_made="Toyota",
            customer_mileage="1",
            current_status="in_progress",
            created_at=datetime.utcnow() - timedelta(days=10),
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.add(
        Worker(
            employee_id="E1",
            first_name="Ali",
            last_name="Khan",
            phone="0300",
            address="x",
            cnic="12345-1234567-1",
            date_of_birth=date(1990, 1, 1),
            hire_date=date(2020, 1, 1),
            position="Tech",
            department="Workshop",
            status="active",
            branch_id=DEFAULT_BRANCH_ID,
        )
    )
    db.commit()

    payload = build_dashboard(db, _U("admin"), period="month")
    assert payload["view"] == "manager"
    labels = {k["label"]: k for k in payload["kpis"]}
    assert "Revenue (invoiced)" in labels
    assert "Cash received" in labels
    assert labels["Revenue (invoiced)"]["value"] == 1000
    assert labels["Cash received"]["value"] == 250
    assert labels["Revenue (invoiced)"]["value"] != labels["Cash received"]["value"]
    assert payload["sections"]["cash_bank"]["position"] == 200  # 250 - 50
    assert payload["sections"]["repairs"]["overdue_count"] >= 1
    assert any(a["code"] == "overdue_jobs" for a in payload["alerts"])


def test_technician_view_hides_finance(db: Session):
    payload = build_dashboard(db, _U("technician"), period="day")
    assert payload["view"] == "technician"
    labels = [k["label"] for k in payload["kpis"]]
    assert "Revenue (invoiced)" not in labels
    assert "Cash received" not in labels
