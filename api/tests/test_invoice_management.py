"""Invoice management: totals, accrual vs cash, credit notes, duplicate RO guard."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.customer_ar import (
    assert_no_duplicate_invoice_for_ro,
    create_credit_note,
    invoice_money_snapshot,
    post_accrual_on_finalize,
    post_payment_credit,
    rebuild_invoice_totals,
)
from app.invoice_math import (
    calculate_invoice_status,
    calculate_totals,
    invoice_amount_due,
    invoice_amount_paid,
    invoice_amount_remaining,
)


def test_calculate_totals_parts_and_labour():
    assert calculate_totals(
        [{"price": 100, "quantity": 2}, {"price": 50, "quantity": 1}],
        [{"price": 500}],
    ) == 750.0


def test_due_paid_remaining_and_status():
    inv = SimpleNamespace(
        net_total=1000.0,
        include_tax=True,
        tax_amount=100.0,
        discount=50.0,
        advance=200.0,
        paid_amount=300.0,
        balance=0,
        type_of="invoice",
    )
    assert invoice_amount_due(inv) == 1050.0
    assert invoice_amount_paid(inv) == 500.0
    assert invoice_amount_remaining(inv) == 550.0
    inv.balance = 550.0
    assert calculate_invoice_status(inv) == "partially_paid"
    inv.paid_amount = 850.0
    inv.balance = invoice_amount_remaining(inv)
    assert calculate_invoice_status(inv) == "paid"


def test_rebuild_totals_after_rejected_lines():
    inv = SimpleNamespace(
        net_total=0,
        discount=0,
        advance=0,
        paid_amount=0,
        tax_amount=0,
        include_tax=False,
        balance=0,
        type_of="invoice",
        status="unpaid",
        items=[
            SimpleNamespace(price=100, quantity=2, approval_status="approved"),
            SimpleNamespace(price=80, quantity=1, approval_status="rejected"),
        ],
        labours=[SimpleNamespace(price=400, approval_status="approved")],
    )
    rebuild_invoice_totals(inv)
    assert inv.net_total == 600.0
    assert inv.status == "unpaid"


def test_duplicate_invoice_for_ro_blocked():
    db = MagicMock()
    existing = SimpleNamespace(id=9, document_no="INV-00009")
    chain = db.query.return_value
    chain.filter.return_value = chain
    chain.first.return_value = existing
    with pytest.raises(HTTPException) as ei:
        assert_no_duplicate_invoice_for_ro(db, repair_order_id=3)
    assert ei.value.status_code == 409


def test_payment_does_not_change_net_total():
    db = MagicMock()
    chain = db.query.return_value
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.first.return_value = None

    inv = SimpleNamespace(
        id=1,
        document_no="INV-00001",
        type_of="invoice",
        customer_id=5,
        net_total=1000.0,
        include_tax=False,
        tax_amount=0,
        discount=0,
        advance=0,
        paid_amount=0,
        balance=1000,
        status="unpaid",
    )
    pay = post_payment_credit(db, inv, amount=400, username="acct")
    assert float(pay.credit) == 400.0
    assert inv.net_total == 1000.0


def test_credit_note_reduces_due():
    db = MagicMock()
    chain = db.query.return_value
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.first.return_value = None

    inv = SimpleNamespace(
        id=2,
        document_no="INV-00002",
        type_of="invoice",
        customer_id=7,
        net_total=500.0,
        include_tax=False,
        tax_amount=0,
        discount=0.0,
        advance=0,
        paid_amount=0,
        balance=500,
        status="unpaid",
        locked_at=None,
        repair_order_id=None,
        job_card_id=None,
        car_id=None,
    )
    note, entry = create_credit_note(db, inv, amount=100, reason="Price adjustment", username="mgr")
    assert note.amount == 100
    assert inv.discount == 100.0
    assert invoice_amount_due(inv) == 400.0
    assert entry is not None
    snap = invoice_money_snapshot(inv)
    assert snap["amount_due"] == 400.0
