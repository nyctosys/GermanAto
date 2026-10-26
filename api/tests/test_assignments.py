"""Worker assignment & scheduling: conflicts, leave, work-time ≠ attendance."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.assignments import (
    create_assignment,
    create_leave,
    find_conflicts,
    record_work_time,
    set_worker_skills,
    suggest_workers,
    workload_for,
)
from app.db import Base
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import current_branch_id, current_reason, current_user_obj
from app.foundation.hooks import install_foundation_hooks
from app.models import AttendanceRecord, JobCard, Worker, WorkTimeEntry


@pytest.fixture()
def db(tmp_path, monkeypatch):
    install_foundation_hooks()
    monkeypatch.setattr("app.log_utils.UPLOAD_FOLDER", str(tmp_path / "uploads"))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    t1 = current_branch_id.set(DEFAULT_BRANCH_ID)
    t2 = current_reason.set("assignment test")
    t3 = current_user_obj.set(
        SimpleNamespace(id=1, username="manager", role="manager")
    )
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        current_branch_id.reset(t1)
        current_reason.reset(t2)
        current_user_obj.reset(t3)


def _worker(db, *, employee_id="E1", skills=None, status="active"):
    w = Worker(
        employee_id=employee_id,
        first_name="Ali",
        last_name="Khan",
        phone="0300",
        address="Lahore",
        cnic=f"35202-{employee_id}-1",
        date_of_birth=date(1990, 1, 1),
        hire_date=date(2020, 1, 1),
        position="Technician",
        department="Workshop",
        status=status,
    )
    db.add(w)
    db.flush()
    if skills is not None:
        set_worker_skills(db, w, skills)
    return w


def _user():
    return SimpleNamespace(id=1, username="manager", role="manager")


def test_skills_and_suggestions(db):
    a = _worker(db, employee_id="A1", skills=["electrical", "ac"])
    b = _worker(db, employee_id="B1", skills=["body"])
    ranked = suggest_workers(db, required_skills=["electrical"])
    ids = [r["id"] for r in ranked]
    assert a.id in ids
    assert ranked[0]["id"] == a.id
    assert "electrical" in ranked[0]["matched_skills"]
    assert b.id in ids


def test_leave_blocks_availability(db):
    w = _worker(db, employee_id="L1", skills=["mech"])
    create_leave(
        db,
        {
            "worker_id": w.id,
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=2)).isoformat(),
            "status": "approved",
        },
        _user(),
    )
    wl = workload_for(db, w.id)
    assert wl["on_leave_today"] is True
    conflicts = find_conflicts(
        db,
        w.id,
        estimated_start_at=datetime.utcnow(),
        estimated_completion_at=datetime.utcnow() + timedelta(hours=4),
    )
    assert conflicts["has_conflict"] is True
    assert conflicts["on_leave"]


def test_overlapping_assignment_requires_override(db):
    w = _worker(db, employee_id="C1")
    card = JobCard(
        customer_name="Cust",
        customer_phone="0300",
        customer_reg_no="ABC",
        customer_made="Civic",
        status="open",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(card)
    db.flush()
    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=6)
    create_assignment(
        db,
        {
            "worker_id": w.id,
            "job_card_id": card.id,
            "estimated_start_at": start,
            "estimated_completion_at": end,
        },
        _user(),
    )
    card2 = JobCard(
        customer_name="Cust2",
        customer_phone="0301",
        customer_reg_no="DEF",
        customer_made="City",
        status="open",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(card2)
    db.flush()
    with pytest.raises(HTTPException) as ei:
        create_assignment(
            db,
            {
                "worker_id": w.id,
                "job_card_id": card2.id,
                "estimated_start_at": start + timedelta(hours=1),
                "estimated_completion_at": end + timedelta(hours=1),
            },
            _user(),
        )
    assert ei.value.status_code == 409
    detail = ei.value.detail
    assert isinstance(detail, dict)
    assert detail.get("override_kind") == "assignment_conflict"

    # Authorized override with reason
    row = create_assignment(
        db,
        {
            "worker_id": w.id,
            "job_card_id": card2.id,
            "estimated_start_at": start + timedelta(hours=1),
            "estimated_completion_at": end + timedelta(hours=1),
            "override_reason": "Manager approved double-book for rush job",
        },
        _user(),
    )
    assert row.override_reason
    assert card2.worker_id == w.id


def test_work_time_separate_from_attendance(db):
    w = _worker(db, employee_id="T1")
    card = JobCard(
        customer_name="Cust",
        customer_phone="0300",
        customer_reg_no="ABC",
        customer_made="Civic",
        status="open",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(card)
    db.add(
        AttendanceRecord(
            worker_id=w.id,
            date=date.today(),
            check_in_time=datetime.utcnow().replace(hour=9, minute=0),
            work_hours=8.0,
            source="zkteco",
        )
    )
    db.flush()
    entry = record_work_time(
        db,
        {
            "worker_id": w.id,
            "job_card_id": card.id,
            "started_at": datetime.utcnow(),
            "ended_at": datetime.utcnow() + timedelta(hours=2),
        },
        _user(),
    )
    assert entry.hours == 2.0
    # Attendance still 8h; repair time is its own table
    att = db.query(AttendanceRecord).filter_by(worker_id=w.id).one()
    assert att.work_hours == 8.0
    assert db.query(WorkTimeEntry).count() == 1
    wl = workload_for(db, w.id)
    assert wl["actual_repair_hours_total"] == 2.0
    assert wl["attendance_today"] is not None
    # Attendance does not alone make someone "available" — leave/status do
    ranked = suggest_workers(db)
    me = next(r for r in ranked if r["id"] == w.id)
    assert "attendance_today" in me


def test_inactive_worker_conflict(db):
    w = _worker(db, employee_id="X1", status="inactive")
    c = find_conflicts(
        db,
        w.id,
        estimated_start_at=datetime.utcnow(),
        estimated_completion_at=datetime.utcnow() + timedelta(hours=2),
    )
    assert c["worker_inactive"] is True
    assert c["has_conflict"] is True


def test_reassign_same_worker_closes_prior_active(db):
    from app.models import WorkAssignment

    w = _worker(db, employee_id="R1")
    card = JobCard(
        customer_name="Cust",
        customer_phone="0300",
        customer_reg_no="ABC",
        customer_made="Civic",
        status="open",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(card)
    db.flush()
    first = create_assignment(
        db, {"worker_id": w.id, "job_card_id": card.id, "priority": "normal"}, _user()
    )
    second = create_assignment(
        db,
        {
            "worker_id": w.id,
            "job_card_id": card.id,
            "priority": "high",
            "notes": "updated window",
        },
        _user(),
    )
    db.flush()
    db.refresh(first)
    assert first.status == "reassigned"
    assert second.status == "assigned"
    assert second.priority == "high"
    active = (
        db.query(WorkAssignment)
        .filter(
            WorkAssignment.job_card_id == card.id,
            WorkAssignment.status.in_(("assigned", "in_progress")),
        )
        .count()
    )
    assert active == 1
