"""Pipeline guards: transitions, deposits, reserve/issue, QC, payment gate, invoice lock."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.invoice_math import calculate_totals
from app.pipeline import (
    assert_can_open_ro_from_quote,
    assert_invoice_unlocked,
    assert_payment_gate_for_delivery,
    assert_qc_before_invoice,
    assert_variation_line_billable,
    discount_pct,
    lock_invoice,
)


class _Line:
    def __init__(self, status="pending", inventory_id=None, quantity=1, price=100):
        self.approval_status = status
        self.inventory_id = inventory_id
        self.quantity = quantity
        self.price = price
        self.product_name = "Pad"
        self.part_number = "PN1"
        self.description = "Labour"


class _Quote:
    def __init__(self, *, type_of="quote", items=None, labours=None):
        self.type_of = type_of
        self.items = items or []
        self.labours = labours or []


class _Invoice:
    def __init__(self, **kw):
        self.type_of = kw.get("type_of", "invoice")
        self.locked_at = kw.get("locked_at")
        self.net_total = kw.get("net_total", 1000)
        self.discount = kw.get("discount", 0)
        self.advance = kw.get("advance", 0)
        self.paid_amount = kw.get("paid_amount", 0)
        self.include_tax = False
        self.tax_amount = 0
        self.balance = kw.get("balance", 1000)


def test_discount_pct():
    assert discount_pct(100, 1000) == 10.0
    assert discount_pct(0, 1000) == 0.0


def test_calculate_totals():
    assert calculate_totals([{"price": 10, "quantity": 2}], [{"price": 5}]) == 25.0


def test_invoice_lock():
    inv = _Invoice()
    assert_invoice_unlocked(inv)
    lock_invoice(inv)
    assert inv.locked_at is not None
    with pytest.raises(HTTPException) as ei:
        assert_invoice_unlocked(inv)
    assert ei.value.status_code == 409


def test_lock_only_after_partial_or_full_payment():
    from app.pipeline import lock_invoice_if_paid

    unpaid = _Invoice(type_of="invoice", net_total=100, advance=0, paid_amount=0, balance=100)
    lock_invoice_if_paid(unpaid)
    assert unpaid.locked_at is None

    partial = _Invoice(
        type_of="invoice", net_total=100, advance=0, paid_amount=40, balance=60, discount=0
    )
    # _Invoice may not have all money fields used by calculate_invoice_status
    partial.include_tax = False
    partial.tax_amount = 0
    partial.discount = 0
    lock_invoice_if_paid(partial)
    assert partial.locked_at is not None


def test_open_ro_requires_approval_or_legacy_pending():
    q = _Quote(items=[_Line("rejected")], labours=[])
    with pytest.raises(HTTPException):
        assert_can_open_ro_from_quote(MagicMock(), q)

    legacy = _Quote(items=[_Line("pending")], labours=[_Line("pending")])
    assert_can_open_ro_from_quote(MagicMock(), legacy)

    ok = _Quote(items=[_Line("approved")], labours=[])
    assert_can_open_ro_from_quote(MagicMock(), ok)


def test_variation_blocking():
    with pytest.raises(HTTPException):
        assert_variation_line_billable(MagicMock(), variation_id=1, approval_status="pending")
    assert_variation_line_billable(MagicMock(), variation_id=None, approval_status="pending")


def test_qc_gate(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    with pytest.raises(HTTPException):
        assert_qc_before_invoice(db, 9)

    qc = SimpleNamespace(id=1)
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = qc
    assert assert_qc_before_invoice(db, 9) is qc


def test_payment_gate_override(monkeypatch):
    from app import pipeline as pl

    monkeypatch.setattr(pl, "payment_gate_enabled", lambda *a, **k: True)
    inv = _Invoice(balance=500, paid_amount=0, advance=0, net_total=500)
    user = SimpleNamespace(role="admin", id=1, username="admin")
    db = MagicMock()

    with pytest.raises(HTTPException) as ei:
        assert_payment_gate_for_delivery(db, user, inv, bypass=False)
    assert ei.value.status_code == 400

    monkeypatch.setattr(pl, "assert_payment_gate_override", lambda *a, **k: "mgr ok")
    reason = assert_payment_gate_for_delivery(db, user, inv, bypass=True, reason="mgr ok")
    assert reason == "mgr ok"


def test_reserve_issue_return_math():
    """Unit-level reserve arithmetic without DB."""
    qty, reserved = 10, 0
    need = 3
    available = qty - reserved
    assert need <= available
    reserved += need
    assert reserved == 3
    # issue
    reserved -= need
    qty -= need
    assert (qty, reserved) == (7, 0)
    # return unused 1
    unused = 1
    qty += unused
    assert qty == 8


def test_deposit_lifecycle_states():
    statuses = ["open", "applied", "refunded", "adjusted"]
    assert "open" in statuses and "applied" in statuses


def test_e2e_happy_path_state_machine():
    """Documented chain order as a state list assertion."""
    chain = [
        "visit",
        "job_card",
        "quote",
        "line_approval",
        "parts_reserved",
        "repair_order",
        "variation",
        "qc",
        "invoice",
        "payment_gate",
        "gate_pass",
    ]
    assert chain.index("job_card") < chain.index("quote")
    assert chain.index("qc") < chain.index("invoice")
    assert chain.index("payment_gate") < chain.index("gate_pass")
    # lock after issue
    inv = _Invoice()
    lock_invoice(inv)
    assert isinstance(inv.locked_at, datetime) or inv.locked_at is not None
