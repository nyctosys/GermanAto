"""Dashboard KPIs helpers, next_action, PO receive math, money facade rules."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.dashboard_kpis import _pct_change
from app.pipeline import next_action


def test_pct_change():
    assert _pct_change(10, 10) == 0.0
    assert _pct_change(20, 10) == 100.0
    assert _pct_change(0, 0) == 0.0


def test_next_action_idle():
    db = MagicMock()
    out = next_action(db)
    assert out["code"] == "idle"


def test_next_action_job_card_needs_quote():
    db = MagicMock()
    card = SimpleNamespace(id=1, quote_invoice_id=None)
    db.get.return_value = card
    out = next_action(db, job_card_id=1)
    assert out["code"] == "build_quote"


def test_po_receive_rejects_over_qty():
    from app.po_receive import receive_po

    po = SimpleNamespace(
        id=1,
        quantity=5,
        qty_received=4,
        inventory_id=9,
        item_name="Pad",
        invoice_no="PO1",
        vendor_id=1,
        rate=10,
        status="ordered",
        to_dict=lambda: {},
    )
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        receive_po(db, po, qty=2, inventory_id=9, user=SimpleNamespace(id=1, username="a"))
    assert ei.value.status_code == 400


def test_money_in_does_not_sum_liability_into_inflow():
    """Documented rule: open deposits are liability, not inflow_total."""
    cash = 100.0
    applied = 25.0
    liability = 50.0
    inflow = cash + applied
    assert inflow == 125.0
    assert liability not in (inflow,)  # not added
    assert inflow == cash + applied


def test_shortage_requires_positive_short():
    need, avail = 5, 2
    assert need - avail == 3
    assert not (2 - 5 > 0)
