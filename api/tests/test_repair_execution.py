"""Repair execution: time clock, labour cost, approval gate, stock issue/return guards."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.repair_execution import (
    _close_entry,
    _rate_for,
    _recalc_labour_cost,
    issue_parts,
    record_manual_hours,
    start_labour,
)


class FakeLab:
    def __init__(self, **kw):
        self.id = kw.get("id", 1)
        self.repair_order_id = kw.get("repair_order_id", 10)
        self.description = "Brake job"
        self.status = kw.get("status", "Approved")
        self.approval_status = kw.get("approval_status", "approved")
        self.from_variation_id = kw.get("from_variation_id")
        self.labour_code_id = kw.get("labour_code_id")
        self.labour_rate = kw.get("labour_rate", 500.0)
        self.actual_hours = kw.get("actual_hours", 0.0)
        self.labour_cost = 0.0
        self.started_at = None
        self.paused_at = None
        self.completed_at = None
        self.assigned_worker_id = None
        self.line_notes = None
        self.std_hours = 1.0


class FakeRO:
    def __init__(self):
        self.id = 10
        self.current_status = "in_progress"
        self.worker_id = 1
        self.branch_id = "a1b2c3d4"
        self.labour = []
        self.parts = []
        self.labour_cost_total = 0.0
        self.parts_cost_total = 0.0
        self.notes = None
        self.deleted_at = None


class FakePart:
    def __init__(self, **kw):
        self.id = kw.get("id", 1)
        self.repair_order_id = 10
        self.inventory_id = kw.get("inventory_id", 1)
        self.description = "Pad"
        self.part_number = "PN1"
        self.quantity = kw.get("quantity", 2)
        self.qty_issued = kw.get("qty_issued", 0)
        self.qty_returned = 0
        self.qty_reserved = 0
        self.status = "pending"
        self.approval_status = "approved"
        self.from_variation_id = None
        self.ownership_type = "shop_stock"
        self.unit_cost = 100.0
        self.deleted_at = None
        self.old_parts_returned = False


def test_labour_cost_uses_rate_times_hours():
    lab = FakeLab(labour_rate=1000.0, actual_hours=2.5)
    db = MagicMock()
    _recalc_labour_cost(db, lab)
    assert lab.labour_cost == 2500.0


def test_rate_fallback_to_labour_code():
    lab = FakeLab(labour_rate=None, labour_code_id=5)
    db = MagicMock()
    db.get.return_value = SimpleNamespace(rate=750.0, standard_hours=1.0)
    assert _rate_for(db, lab) == 750.0


def test_close_entry_hours():
    start = datetime.utcnow() - timedelta(hours=2)
    entry = SimpleNamespace(started_at=start, ended_at=None, status="open", hours=0.0)
    hours = _close_entry(entry, at=start + timedelta(hours=2))
    assert entry.status == "closed"
    assert abs(hours - 2.0) < 0.01


def test_duplicate_start_blocked(monkeypatch):
    ro = FakeRO()
    lab = FakeLab()
    user = SimpleNamespace(username="tech1", id=1)
    db = MagicMock()

    monkeypatch.setattr("app.repair_execution.get_labour", lambda *_a, **_k: lab)
    monkeypatch.setattr(
        "app.repair_execution._open_time_entry",
        lambda *_a, **_k: SimpleNamespace(id=99, status="open"),
    )
    monkeypatch.setattr("app.repair_execution._assert_labour_workable", lambda *_a, **_k: None)

    with pytest.raises(HTTPException) as ei:
        start_labour(db, ro, lab.id, user)
    assert ei.value.status_code == 409


def test_unapproved_variation_work_blocked(monkeypatch):
    from app.repair_execution import _assert_labour_workable

    lab = FakeLab(from_variation_id=3, approval_status="pending")
    db = MagicMock()
    db.get.return_value = SimpleNamespace(status="sent")
    with pytest.raises(HTTPException):
        _assert_labour_workable(db, lab)


def test_manual_hours_auto_pauses_running_clock(monkeypatch):
    ro = FakeRO()
    lab = FakeLab(status="in_progress", actual_hours=0.5)
    user = SimpleNamespace(username="tech1", id=1)
    db = MagicMock()
    open_entry = SimpleNamespace(
        id=1,
        started_at=datetime.utcnow() - timedelta(hours=1),
        ended_at=None,
        status="open",
        hours=0.0,
    )

    monkeypatch.setattr("app.repair_execution.get_labour", lambda *_a, **_k: lab)
    monkeypatch.setattr("app.repair_execution._open_time_entry", lambda *_a, **_k: open_entry)
    monkeypatch.setattr("app.repair_execution._assert_labour_workable", lambda *_a, **_k: None)
    monkeypatch.setattr("app.repair_execution._recalc_labour_cost", lambda *_a, **_k: None)
    monkeypatch.setattr("app.repair_execution._recalc_ro_costs", lambda *_a, **_k: None)
    monkeypatch.setattr("app.repair_execution.audit_write", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.repair_execution._labour_dict",
        lambda *_a, **_k: {"id": lab.id, "actual_hours": lab.actual_hours, "status": lab.status},
    )
    monkeypatch.setattr(
        "app.repair_execution.RepairTimeEntry",
        lambda **kw: SimpleNamespace(to_dict=lambda: kw, **kw),
    )

    result = record_manual_hours(db, ro, lab.id, user, hours=0.25)
    assert open_entry.status == "closed"
    assert result["auto_paused_hours"] > 0
    assert abs(lab.actual_hours - (0.5 + result["auto_paused_hours"] + 0.25)) < 0.02
    assert lab.status == "paused"


def test_manual_hours_replace_sets_total(monkeypatch):
    ro = FakeRO()
    lab = FakeLab(status="paused", actual_hours=3.0)
    user = SimpleNamespace(username="tech1", id=1)
    db = MagicMock()

    monkeypatch.setattr("app.repair_execution.get_labour", lambda *_a, **_k: lab)
    monkeypatch.setattr("app.repair_execution._open_time_entry", lambda *_a, **_k: None)
    monkeypatch.setattr("app.repair_execution._assert_labour_workable", lambda *_a, **_k: None)
    monkeypatch.setattr("app.repair_execution._recalc_labour_cost", lambda *_a, **_k: None)
    monkeypatch.setattr("app.repair_execution._recalc_ro_costs", lambda *_a, **_k: None)
    monkeypatch.setattr("app.repair_execution.audit_write", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.repair_execution._labour_dict",
        lambda *_a, **_k: {"id": lab.id, "actual_hours": lab.actual_hours},
    )
    monkeypatch.setattr(
        "app.repair_execution.RepairTimeEntry",
        lambda **kw: SimpleNamespace(to_dict=lambda: kw, **kw),
    )

    record_manual_hours(db, ro, lab.id, user, hours=1.5, replace=True)
    assert lab.actual_hours == 1.5


def test_ensure_stock_audit_reason_sets_default(monkeypatch):
    from app.foundation.context import get_reason, set_reason
    from app.repair_execution import _ensure_stock_audit_reason

    token = set_reason(None)
    try:
        assert not (get_reason() or "").strip()
        _ensure_stock_audit_reason(FakeRO(), action="Issue parts")
        assert get_reason() == "Issue parts for RO #10"
        set_reason("Already set")
        _ensure_stock_audit_reason(FakeRO(), action="Issue parts")
        assert get_reason() == "Already set"
    finally:
        set_reason(None)
        del token


def test_issue_fully_issued_duplicate_blocked(monkeypatch):
    ro = FakeRO()
    part = FakePart(quantity=2, qty_issued=2)
    user = SimpleNamespace(username="store", id=2)
    db = MagicMock()
    monkeypatch.setattr("app.repair_execution.get_part", lambda *_a, **_k: part)
    monkeypatch.setattr("app.repair_execution._assert_part_workable", lambda *_a, **_k: None)
    with pytest.raises(HTTPException) as ei:
        issue_parts(db, ro, part.id, user)  # no qty → remaining 0 → 409
    assert ei.value.status_code == 409
    with pytest.raises(HTTPException) as ei2:
        issue_parts(db, ro, part.id, user, qty=1)
    assert ei2.value.status_code == 400


def test_payroll_separation_documented():
    """Repair hours must not be confused with attendance payroll hours."""
    import app.repair_execution as mod

    assert "payroll" in (mod.__doc__ or "").lower()
