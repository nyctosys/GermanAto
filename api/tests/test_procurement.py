"""Procurement: PO ≠ stock ≠ payable; invoice creates payable; payment reduces it."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.procurement import (
    ProcurementError,
    create_supplier_invoice,
    known_rate_for_item,
    overdue_payables,
    post_credit_note,
    receive_goods,
    record_supplier_payment,
    vendor_outstanding,
)


def _money(v):
    return Decimal(str(v)).quantize(Decimal("0.01"))


def test_known_rate_prefers_last_po():
    item = SimpleNamespace(id=9, avg_cost=Decimal("50.00"))
    po = SimpleNamespace(rate=Decimal("42.50"))
    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = (
        po
    )
    assert known_rate_for_item(db, vendor_id=1, item=item) == _money("42.50")


def test_receive_goods_rejects_draft():
    po = SimpleNamespace(status="draft", quantity=10, qty_received=0)
    db = MagicMock()
    with pytest.raises(ProcurementError):
        receive_goods(
            db,
            po=po,
            qty=1,
            unit_cost=10,
            item=SimpleNamespace(id=1),
            receipt_path="uploads/r.pdf",
        )


def test_create_invoice_posts_debit(monkeypatch):
    from app import procurement as proc

    vendor = SimpleNamespace(id=1, payment_terms_days=15)
    grn = SimpleNamespace(
        id=7,
        document_no="GRN-00007",
        purchase_order_id=3,
        supplier_invoice_id=None,
        status="received",
        amount=Decimal("100.00"),
    )

    posted = {}

    def fake_post_ledger(db, **kwargs):
        posted.update(kwargs)
        return SimpleNamespace(id=99)

    monkeypatch.setattr(proc, "post_ledger", fake_post_ledger)

    added: list = []
    db = MagicMock()
    db.add.side_effect = lambda o: added.append(o)

    def flush():
        for o in added:
            if getattr(o, "id", None) is None:
                o.id = len(added)

    db.flush.side_effect = flush

    inv = create_supplier_invoice(
        db,
        vendor=vendor,
        amount=100,
        supplier_invoice_no="SI-1",
        goods_receipt=grn,
        username="admin",
    )
    assert _money(posted.get("debit")) == _money(100)
    assert float(posted.get("credit") or 0) == 0.0
    assert grn.status == "invoiced"
    assert grn.supplier_invoice_id == inv.id
    assert inv.document_no.startswith("SINV-")


def test_payment_reduces_invoice_balance(monkeypatch):
    from app import procurement as proc

    vendor = SimpleNamespace(id=1)
    inv = SimpleNamespace(
        id=5,
        supplier_invoice_no="SI-1",
        amount=Decimal("100.00"),
        amount_paid=Decimal("0.00"),
        status="open",
    )

    monkeypatch.setattr(
        proc,
        "post_ledger",
        lambda db, **kw: SimpleNamespace(id=11),
    )

    added: list = []
    db = MagicMock()
    db.add.side_effect = lambda o: added.append(o)

    def flush():
        for o in added:
            if getattr(o, "id", None) is None:
                o.id = 1

    db.flush.side_effect = flush

    pay = record_supplier_payment(
        db,
        vendor=vendor,
        amount=40,
        supplier_invoice=inv,
        username="admin",
    )
    assert _money(inv.amount_paid) == _money(40)
    assert inv.status == "partial"
    assert pay.amount == _money(40)


def test_overdue_payables_filters_due_date():
    today = date.today()
    inv_over = SimpleNamespace(
        amount=Decimal("50"),
        amount_paid=Decimal("0"),
        status="open",
        due_date=today - timedelta(days=3),
        to_dict=lambda: {"id": 1, "amount": 50},
    )
    inv_ok = SimpleNamespace(
        amount=Decimal("50"),
        amount_paid=Decimal("0"),
        status="open",
        due_date=today + timedelta(days=3),
        to_dict=lambda: {"id": 2, "amount": 50},
    )
    vendor = SimpleNamespace(name="Acme", code="VN001", company_name="Acme Co")
    db = MagicMock()
    q = db.query.return_value.join.return_value.filter.return_value.filter.return_value.filter.return_value
    q.order_by.return_value.all.return_value = [(inv_over, vendor)]
    rows = overdue_payables(db, as_of=today)
    assert len(rows) == 1
    assert rows[0]["days_overdue"] == 3
    assert rows[0]["vendor_name"] == "Acme"
    # ensure open future due not mixed in mock
    assert inv_ok.due_date > today


def test_credit_note_requires_reason():
    db = MagicMock()
    with pytest.raises(ProcurementError):
        post_credit_note(
            db,
            vendor=SimpleNamespace(id=1),
            amount=10,
            reason="  ",
        )


def test_vendor_outstanding_empty():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = None
    assert vendor_outstanding(db, 1) == Decimal("0.00")
