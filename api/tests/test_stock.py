"""Unit tests for stock ledger: avg cost, GRN, reserve/issue/return, negatives."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.stock import (
    StockError,
    adjust,
    available,
    compute_avg_cost,
    issue_to_ro,
    opening_stock,
    pieces_as_packs,
    po_receive,
    refresh_po_status,
    release,
    reserve,
    return_from_ro,
    to_base_pieces,
    wastage,
)


class FakeItem:
    def __init__(self, quantity=0, reserved=0, avg_cost=0, part_number="PN001", name="Part"):
        self.id = 1
        self.quantity = quantity
        self.reserved = reserved
        self.avg_cost = Decimal(str(avg_cost))
        self.pending_purchase = False
        self.part_number = part_number
        self.name = name
        self.updated_at = None


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def test_compute_avg_cost_empty_stock():
    assert compute_avg_cost(0, 0, 10, "100.00") == Decimal("100.00")


def test_compute_avg_cost_weighted():
    # 10 @ 100 + 10 @ 200 → 20 @ 150
    assert compute_avg_cost(10, "100", 10, "200") == Decimal("150.00")


def test_compute_avg_cost_uneven():
    # 2 @ 50 + 1 @ 80 → 180/3 = 60
    assert compute_avg_cost(2, "50.00", 1, "80.00") == Decimal("60.00")


def test_po_receive_updates_qty_and_avg():
    db = FakeSession()
    item = FakeItem(quantity=10, avg_cost=100)
    txn = po_receive(db, item=item, qty=10, unit_cost=200)
    assert item.quantity == 20
    assert item.avg_cost == Decimal("150.00")
    assert txn.transaction_type == "po_receive"
    assert txn.quantity == 10
    assert len(db.added) == 1


def test_partial_receive_balances():
    db = FakeSession()
    item = FakeItem(quantity=0, avg_cost=0)
    po = SimpleNamespace(id=7, quantity=10, qty_received=0, status="ordered")
    po_receive(db, item=item, qty=4, unit_cost=50, purchase_order=po)
    po.qty_received = 4
    assert refresh_po_status(po) == "partial"
    assert item.quantity == 4
    po_receive(db, item=item, qty=6, unit_cost=50, purchase_order=po)
    po.qty_received = 10
    assert refresh_po_status(po) == "received"
    assert item.quantity == 10


def test_reserve_release_issue_return_balances():
    db = FakeSession()
    item = FakeItem(quantity=10, reserved=0)
    reserve(db, item=item, qty=3, repair_order_id=1)
    assert item.quantity == 10
    assert item.reserved == 3
    assert available(item) == 7

    release(db, item=item, qty=1, repair_order_id=1)
    assert item.reserved == 2

    issue_to_ro(db, item=item, qty=2, repair_order_id=1, from_reserve=True)
    assert item.quantity == 8
    assert item.reserved == 0

    return_from_ro(db, item=item, qty=2, repair_order_id=1)
    assert item.quantity == 10
    assert available(item) == 10


def test_negative_stock_prevented_on_reserve():
    db = FakeSession()
    item = FakeItem(quantity=2, reserved=0)
    with pytest.raises(StockError, match="insufficient available"):
        reserve(db, item=item, qty=5)


def test_negative_stock_prevented_on_issue():
    db = FakeSession()
    item = FakeItem(quantity=1, reserved=1)
    with pytest.raises(StockError):
        issue_to_ro(db, item=item, qty=2, from_reserve=True)


def test_adjustment_requires_reason_and_evidence():
    db = FakeSession()
    item = FakeItem(quantity=5)
    with pytest.raises(StockError, match="reason"):
        adjust(db, item=item, delta=-1, reason="", evidence_path="x.pdf")
    with pytest.raises(StockError, match="evidence"):
        adjust(db, item=item, delta=-1, reason="count", evidence_path=None)
    adjust(db, item=item, delta=-2, reason="cycle count", evidence_path="/uploads/e.pdf")
    assert item.quantity == 3


def test_adjustment_cannot_go_below_reserved():
    db = FakeSession()
    item = FakeItem(quantity=5, reserved=4)
    with pytest.raises(StockError, match="reserved"):
        adjust(db, item=item, delta=-2, reason="shrink", evidence_path="e.pdf")


def test_three_packs_of_ten_are_thirty_pieces():
    assert to_base_pieces(packs=3, pack_size=10) == 30
    assert to_base_pieces(packs=3, pieces=2, pack_size=10) == 32
    assert pieces_as_packs(32, 10) == (3, 2)


def test_opening_stock_logs_confirmed_movement():
    db = FakeSession()
    item = FakeItem(quantity=0, avg_cost=0)
    txn = opening_stock(db, item=item, qty=30, unit_cost=50)
    assert item.quantity == 30
    assert item.avg_cost == __import__("decimal").Decimal("50.00")
    assert txn.transaction_type == "opening"
    assert txn.quantity == 30


def test_wastage_reduces_available_only():
    db = FakeSession()
    item = FakeItem(quantity=20, reserved=5)
    txn = wastage(db, item=item, qty=3, reason="damaged")
    assert item.quantity == 17
    assert item.reserved == 5
    assert txn.transaction_type == "wastage"
    assert txn.quantity == -3
    with pytest.raises(StockError, match="available"):
        wastage(db, item=item, qty=20, reason="too much")
