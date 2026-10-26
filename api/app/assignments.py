"""Worker assignment & scheduling: availability, conflicts, work time (≠ attendance)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.foundation.audit import audit_write
from app.foundation.overrides import require_override
from app.foundation.settings import get_setting
from app.models import (
    AttendanceRecord,
    JobCard,
    RepairOrder,
    Worker,
    WorkerLeave,
    WorkAssignment,
    WorkTimeEntry,
)

ACTIVE_STATUSES = frozenset({"assigned", "in_progress"})
TERMINAL_STATUSES = frozenset({"completed", "cancelled", "reassigned"})


def _parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("T", " ")
    if len(text) == 10:
        text = text + " 00:00:00"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[:19] if fmt.endswith("%S") else text[:16], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError:
        return None


def _window(start: datetime | None, end: datetime | None) -> tuple[datetime, datetime]:
    """Normalize a schedule window; default same-day 8h block if only one side set."""
    now = datetime.utcnow()
    s = start or now
    e = end or (s + timedelta(hours=8))
    if e < s:
        e = s + timedelta(hours=1)
    return s, e


def _overlaps(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> bool:
    return a0 < b1 and b0 < a1


def on_leave(
    db: Session,
    worker_id: int,
    *,
    day: date | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[WorkerLeave]:
    """Approved leave rows overlapping day or [start, end]."""
    q = db.query(WorkerLeave).filter(
        WorkerLeave.worker_id == worker_id,
        WorkerLeave.status == "approved",
    )
    if start and end:
        d0, d1 = start.date(), end.date()
        q = q.filter(WorkerLeave.start_date <= d1, WorkerLeave.end_date >= d0)
    else:
        d = day or date.today()
        q = q.filter(WorkerLeave.start_date <= d, WorkerLeave.end_date >= d)
    return q.all()


def active_assignments(
    db: Session,
    worker_id: int,
    *,
    exclude_ids: set[int] | frozenset[int] | None = None,
) -> list[WorkAssignment]:
    q = db.query(WorkAssignment).filter(
        WorkAssignment.worker_id == worker_id,
        WorkAssignment.status.in_(tuple(ACTIVE_STATUSES)),
    )
    if exclude_ids:
        q = q.filter(~WorkAssignment.id.in_(tuple(exclude_ids)))
    return q.order_by(WorkAssignment.id.asc()).all()


def find_conflicts(
    db: Session,
    worker_id: int,
    *,
    estimated_start_at: datetime | None,
    estimated_completion_at: datetime | None,
    deadline_at: datetime | None = None,
    exclude_assignment_ids: set[int] | frozenset[int] | None = None,
) -> dict[str, Any]:
    """Server-side conflict scan — never based on a page refresh alone.

    Hard conflict: inactive, approved leave, or overlapping *explicit* schedule
    windows. Untimed open assignments are listed as warnings (workload) only.
    """
    new_explicit = any([estimated_start_at, estimated_completion_at, deadline_at])
    start, end = _window(
        estimated_start_at,
        estimated_completion_at or deadline_at,
    )
    leave_rows = on_leave(db, worker_id, start=start, end=end) if new_explicit else on_leave(
        db, worker_id
    )
    overlapping: list[dict] = []
    open_untimed: list[dict] = []
    for row in active_assignments(db, worker_id, exclude_ids=exclude_assignment_ids):
        other_explicit = any(
            [row.estimated_start_at, row.estimated_completion_at, row.deadline_at]
        )
        if new_explicit and other_explicit:
            other_start, other_end = _window(
                row.estimated_start_at,
                row.estimated_completion_at or row.deadline_at,
            )
            if _overlaps(start, end, other_start, other_end):
                overlapping.append(row.to_dict())
        else:
            open_untimed.append(row.to_dict())

    worker = db.get(Worker, worker_id)
    inactive = worker is None or (worker.status or "").lower() != "active"
    hard = bool(leave_rows or overlapping or inactive)
    return {
        "has_conflict": hard,
        "on_leave": [r.to_dict() for r in leave_rows],
        "overlapping_assignments": overlapping,
        "open_assignments_warning": open_untimed,
        "worker_inactive": inactive,
        "window": {
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end.strftime("%Y-%m-%d %H:%M:%S"),
        },
    }


def attendance_today(db: Session, worker_id: int) -> dict | None:
    """Soft signal only — does not decide availability by itself."""
    row = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.worker_id == worker_id,
            AttendanceRecord.date == date.today(),
        )
        .order_by(AttendanceRecord.id.desc())
        .first()
    )
    return row.to_dict() if row else None


def workload_for(db: Session, worker_id: int) -> dict[str, Any]:
    open_rows = active_assignments(db, worker_id)
    overdue = [
        a
        for a in open_rows
        if a.deadline_at and a.deadline_at < datetime.utcnow()
    ]
    open_hours = 0.0
    for a in open_rows:
        s, e = _window(a.estimated_start_at, a.estimated_completion_at or a.deadline_at)
        open_hours += max(0.0, (e - s).total_seconds() / 3600.0)

    repair_hours = (
        db.query(WorkTimeEntry)
        .filter(WorkTimeEntry.worker_id == worker_id)
        .all()
    )
    actual_repair_hours = 0.0
    for e in repair_hours:
        if e.hours is not None:
            actual_repair_hours += float(e.hours)
        elif e.started_at and e.ended_at:
            actual_repair_hours += (e.ended_at - e.started_at).total_seconds() / 3600.0

    return {
        "open_assignment_count": len(open_rows),
        "open_estimated_hours": round(open_hours, 2),
        "overdue_count": len(overdue),
        "overdue_assignment_ids": [a.id for a in overdue],
        "actual_repair_hours_total": round(actual_repair_hours, 2),
        "on_leave_today": bool(on_leave(db, worker_id)),
        "attendance_today": attendance_today(db, worker_id),
        "active_assignments": [a.to_dict() for a in open_rows],
    }


def worker_context(db: Session, worker_id: int) -> dict[str, Any]:
    worker = db.get(Worker, worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    wl = workload_for(db, worker_id)
    available = (
        (worker.status or "").lower() == "active"
        and not wl["on_leave_today"]
    )
    return {
        "worker": worker.to_dict(),
        "skills": worker.skills,
        "available": available,
        "availability_basis": [
            "status==active",
            "not on approved leave today",
            "workload from work_assignments (not page refresh)",
        ],
        "workload": wl,
        "note": "Attendance check-in is informational only; it does not mark a worker available.",
    }


def suggest_workers(
    db: Session,
    *,
    required_skills: list[str] | None = None,
    estimated_start_at: datetime | None = None,
    estimated_completion_at: datetime | None = None,
    deadline_at: datetime | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Rank active workers by skill match, leave, conflicts, then open load."""
    skills_needed = [s.strip().lower() for s in (required_skills or []) if s and str(s).strip()]
    workers = (
        db.query(Worker)
        .filter(Worker.status == "active")
        .order_by(Worker.first_name, Worker.last_name)
        .all()
    )
    ranked: list[dict[str, Any]] = []
    for w in workers:
        conflicts = find_conflicts(
            db,
            w.id,
            estimated_start_at=estimated_start_at,
            estimated_completion_at=estimated_completion_at,
            deadline_at=deadline_at,
        )
        wl = workload_for(db, w.id)
        have = {s.lower() for s in w.skills}
        matched = [s for s in skills_needed if s in have] if skills_needed else list(w.skills)
        skill_score = len(matched) if skills_needed else 0
        score = 100
        score += skill_score * 15
        if conflicts["has_conflict"]:
            score -= 50
        if wl["on_leave_today"]:
            score -= 80
        score -= wl["open_assignment_count"] * 8
        score -= wl["overdue_count"] * 12
        ranked.append(
            {
                "id": w.id,
                "employee_id": w.employee_id,
                "first_name": w.first_name,
                "last_name": w.last_name,
                "name": f"{w.first_name} {w.last_name}".strip(),
                "position": w.position,
                "skills": w.skills,
                "matched_skills": matched,
                "available": not conflicts["has_conflict"] and not wl["on_leave_today"],
                "conflict": conflicts,
                "workload": {
                    "open_assignment_count": wl["open_assignment_count"],
                    "open_estimated_hours": wl["open_estimated_hours"],
                    "overdue_count": wl["overdue_count"],
                },
                "attendance_today": wl["attendance_today"],
                "suggestion_score": score,
            }
        )
    ranked.sort(key=lambda r: (-r["suggestion_score"], r["name"].lower()))
    return ranked[: max(1, min(limit, 100))]


def _notify_assignment(db: Session, user, assignment: WorkAssignment, action: str) -> None:
    channels = get_setting(db, "assignment_notify_channels") or ["log"]
    if not isinstance(channels, list):
        channels = ["log"]
    if "log" in channels or not channels:
        audit_write(
            db,
            user=user,
            action=action,
            module="assignments",
            reference_id=assignment.id,
            details=(
                f"worker={assignment.worker_id} jc={assignment.job_card_id} "
                f"ro={assignment.repair_order_id} status={assignment.status}"
            ),
            new_value=assignment.to_dict(),
            reason=assignment.override_reason,
        )


def create_assignment(
    db: Session,
    data: dict[str, Any],
    user,
    *,
    allow_conflict_override: bool = True,
) -> WorkAssignment:
    worker_id = data.get("worker_id")
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    worker = db.get(Worker, int(worker_id))
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    est_start = _parse_dt(data.get("estimated_start_at"))
    est_end = _parse_dt(data.get("estimated_completion_at"))
    deadline = _parse_dt(data.get("deadline_at"))
    job_card_id = data.get("job_card_id")
    repair_order_id = data.get("repair_order_id")
    if job_card_id:
        if not db.get(JobCard, int(job_card_id)):
            raise HTTPException(status_code=404, detail="Job card not found")
    if repair_order_id:
        if not db.get(RepairOrder, int(repair_order_id)):
            raise HTTPException(status_code=404, detail="Repair order not found")

    # Rows we will supersede on this document — exclude from conflict scan so
    # updating times/priority for the same JC/RO does not 409 against itself.
    prior_q = db.query(WorkAssignment).filter(WorkAssignment.status.in_(tuple(ACTIVE_STATUSES)))
    if job_card_id:
        prior_q = prior_q.filter(WorkAssignment.job_card_id == int(job_card_id))
    elif repair_order_id:
        prior_q = prior_q.filter(WorkAssignment.repair_order_id == int(repair_order_id))
    else:
        prior_q = prior_q.filter(False)
    prior_rows = prior_q.all()
    prior_ids = {p.id for p in prior_rows}

    conflicts = find_conflicts(
        db,
        int(worker_id),
        estimated_start_at=est_start,
        estimated_completion_at=est_end,
        deadline_at=deadline,
        exclude_assignment_ids=prior_ids,
    )
    override_reason = (data.get("override_reason") or data.get("reason") or "").strip() or None
    if conflicts["has_conflict"]:
        if not allow_conflict_override or not override_reason:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Assignment conflicts with leave or overlapping work",
                    "conflict": conflicts,
                    "require_reason": True,
                    "override_kind": "assignment_conflict",
                },
            )
        override_reason = require_override(
            db, user, "assignment_conflict", reason=override_reason
        )

    for prior in prior_rows:
        prior.status = "reassigned"
        prior.updated_at = datetime.utcnow()

    assignment = WorkAssignment(
        worker_id=int(worker_id),
        job_card_id=int(job_card_id) if job_card_id else None,
        repair_order_id=int(repair_order_id) if repair_order_id else None,
        status=(data.get("status") or "assigned").strip() or "assigned",
        priority=(data.get("priority") or "normal").strip() or "normal",
        estimated_start_at=est_start,
        estimated_completion_at=est_end,
        deadline_at=deadline,
        override_reason=override_reason,
        notes=(data.get("notes") or None),
        assigned_by=getattr(user, "username", None),
    )
    db.add(assignment)
    db.flush()

    # Mirror onto job card / RO legacy fields for existing UI
    if assignment.job_card_id:
        card = db.get(JobCard, assignment.job_card_id)
        if card:
            card.worker_id = assignment.worker_id
            if data.get("team_name") is not None:
                card.team_name = data.get("team_name") or None
            if deadline and hasattr(card, "expected_completion_at"):
                card.expected_completion_at = deadline
            if data.get("priority") and hasattr(card, "priority"):
                card.priority = assignment.priority

    if assignment.repair_order_id:
        ro = db.get(RepairOrder, assignment.repair_order_id)
        if ro:
            name = f"{worker.first_name} {worker.last_name}".strip()
            ro.worker_id = assignment.worker_id
            ro.worker_name = name
            existing = []
            if ro.workers_json:
                try:
                    existing = json.loads(ro.workers_json) or []
                except Exception:
                    existing = []
            ids = {int(x.get("id")) for x in existing if isinstance(x, dict) and x.get("id")}
            if assignment.worker_id not in ids:
                existing.append({"id": assignment.worker_id, "name": name})
            ro.workers_json = json.dumps(existing)

    _notify_assignment(db, user, assignment, "assignment.create")
    return assignment


def update_assignment_status(
    db: Session,
    assignment_id: int,
    data: dict[str, Any],
    user,
) -> WorkAssignment:
    row = db.get(WorkAssignment, assignment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")
    status = (data.get("status") or "").strip()
    if status:
        if status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        row.status = status
        if status == "in_progress" and not row.actual_start_at:
            row.actual_start_at = datetime.utcnow()
        if status in ("completed", "cancelled") and not row.actual_end_at:
            row.actual_end_at = datetime.utcnow()
    for key in (
        "priority",
        "notes",
        "estimated_start_at",
        "estimated_completion_at",
        "deadline_at",
    ):
        if key not in data:
            continue
        if key.endswith("_at"):
            setattr(row, key, _parse_dt(data.get(key)))
        else:
            setattr(row, key, data.get(key))
    row.updated_at = datetime.utcnow()
    _notify_assignment(db, user, row, "assignment.update")
    return row


def reassign(
    db: Session,
    assignment_id: int,
    data: dict[str, Any],
    user,
) -> WorkAssignment:
    old = db.get(WorkAssignment, assignment_id)
    if not old:
        raise HTTPException(status_code=404, detail="Assignment not found")
    payload = {
        "worker_id": data.get("worker_id"),
        "job_card_id": old.job_card_id,
        "repair_order_id": old.repair_order_id,
        "priority": data.get("priority", old.priority),
        "estimated_start_at": data.get("estimated_start_at") or old.estimated_start_at,
        "estimated_completion_at": data.get("estimated_completion_at")
        or old.estimated_completion_at,
        "deadline_at": data.get("deadline_at") or old.deadline_at,
        "notes": data.get("notes"),
        "override_reason": data.get("override_reason") or data.get("reason"),
        "team_name": data.get("team_name"),
    }
    old.status = "reassigned"
    old.updated_at = datetime.utcnow()
    return create_assignment(db, payload, user)


def record_work_time(
    db: Session,
    data: dict[str, Any],
    user,
) -> WorkTimeEntry:
    worker_id = data.get("worker_id")
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    if not data.get("repair_order_id") and not data.get("job_card_id"):
        raise HTTPException(
            status_code=400, detail="repair_order_id or job_card_id is required"
        )
    started = _parse_dt(data.get("started_at")) or datetime.utcnow()
    ended = _parse_dt(data.get("ended_at"))
    hours = data.get("hours")
    if hours is None and ended:
        hours = round((ended - started).total_seconds() / 3600.0, 2)
    entry = WorkTimeEntry(
        worker_id=int(worker_id),
        repair_order_id=int(data["repair_order_id"]) if data.get("repair_order_id") else None,
        job_card_id=int(data["job_card_id"]) if data.get("job_card_id") else None,
        started_at=started,
        ended_at=ended,
        hours=float(hours) if hours is not None else None,
        notes=data.get("notes"),
        created_by_user=getattr(user, "username", None),
    )
    db.add(entry)
    db.flush()
    audit_write(
        db,
        user=user,
        action="work_time.create",
        module="assignments",
        reference_id=entry.id,
        details=f"repair time (not attendance) worker={entry.worker_id}",
        new_value=entry.to_dict(),
    )
    return entry


def list_assignments(
    db: Session,
    *,
    worker_id: int | None = None,
    job_card_id: int | None = None,
    repair_order_id: int | None = None,
    status: str | None = None,
    overdue_only: bool = False,
    limit: int = 100,
) -> list[WorkAssignment]:
    q = db.query(WorkAssignment)
    if worker_id:
        q = q.filter(WorkAssignment.worker_id == worker_id)
    if job_card_id:
        q = q.filter(WorkAssignment.job_card_id == job_card_id)
    if repair_order_id:
        q = q.filter(WorkAssignment.repair_order_id == repair_order_id)
    if status:
        q = q.filter(WorkAssignment.status == status)
    if overdue_only:
        q = q.filter(
            WorkAssignment.status.in_(tuple(ACTIVE_STATUSES)),
            WorkAssignment.deadline_at.isnot(None),
            WorkAssignment.deadline_at < datetime.utcnow(),
        )
    return q.order_by(WorkAssignment.id.desc()).limit(limit).all()


def set_worker_skills(db: Session, worker: Worker, skills: list[str] | None) -> None:
    if skills is None:
        return
    cleaned = [str(s).strip() for s in skills if str(s).strip()]
    worker.skills_json = json.dumps(cleaned)


def create_leave(db: Session, data: dict[str, Any], user) -> WorkerLeave:
    worker_id = data.get("worker_id")
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    start = data.get("start_date")
    end = data.get("end_date")
    if not start or not end:
        raise HTTPException(status_code=400, detail="start_date and end_date required")
    if isinstance(start, str):
        start = datetime.strptime(start[:10], "%Y-%m-%d").date()
    if isinstance(end, str):
        end = datetime.strptime(end[:10], "%Y-%m-%d").date()
    if end < start:
        raise HTTPException(status_code=400, detail="end_date before start_date")
    row = WorkerLeave(
        worker_id=int(worker_id),
        start_date=start,
        end_date=end,
        leave_type=(data.get("leave_type") or "annual").strip(),
        status=(data.get("status") or "approved").strip(),
        notes=data.get("notes"),
        created_by_user=getattr(user, "username", None),
    )
    db.add(row)
    db.flush()
    return row
