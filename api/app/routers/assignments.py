"""Worker assignment & scheduling API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.assignments import (
    create_assignment,
    create_leave,
    list_assignments,
    record_work_time,
    reassign,
    set_worker_skills,
    suggest_workers,
    update_assignment_status,
    worker_context,
    _parse_dt,
)
from app.db import get_db
from app.deps import require_roles
from app.models import Worker, WorkerLeave, WorkTimeEntry

router = APIRouter(tags=["assignments"])

# Managers + reception (service_advisor) may assign; technicians may log work time / view.
_ASSIGN = ["admin", "manager", "service_advisor", "accountant"]
_READ = ["admin", "manager", "service_advisor", "accountant", "technician", "inventory_manager"]
_HR = ["admin", "manager", "accountant"]


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/assignments/suggest")
def suggest(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_READ)),
):
    skills_raw = (request.query_params.get("skills") or "").strip()
    skills = [s.strip() for s in skills_raw.split(",") if s.strip()] if skills_raw else []
    limit = int(request.query_params.get("limit") or 20)
    rows = suggest_workers(
        db,
        required_skills=skills,
        estimated_start_at=_parse_dt(request.query_params.get("estimated_start_at")),
        estimated_completion_at=_parse_dt(
            request.query_params.get("estimated_completion_at")
        ),
        deadline_at=_parse_dt(request.query_params.get("deadline_at")),
        limit=limit,
    )
    return _json({"workers": rows, "basis": "server: status, leave, conflicts, workload"})


@router.get("/assignments")
def list_all(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_READ)),
):
    worker_id = request.query_params.get("worker_id")
    job_card_id = request.query_params.get("job_card_id")
    repair_order_id = request.query_params.get("repair_order_id")
    status = (request.query_params.get("status") or "").strip() or None
    overdue = (request.query_params.get("overdue") or "").lower() in ("1", "true", "yes")
    rows = list_assignments(
        db,
        worker_id=int(worker_id) if worker_id else None,
        job_card_id=int(job_card_id) if job_card_id else None,
        repair_order_id=int(repair_order_id) if repair_order_id else None,
        status=status,
        overdue_only=overdue,
    )
    # Enrich with worker name
    out = []
    for a in rows:
        d = a.to_dict()
        w = db.get(Worker, a.worker_id)
        d["worker_name"] = (
            f"{w.first_name} {w.last_name}".strip() if w else None
        )
        d["worker_skills"] = w.skills if w else []
        out.append(d)
    return _json({"assignments": out})


@router.post("/assignments")
def create(
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_ASSIGN)),
):
    row = create_assignment(db, body or {}, current_user)
    db.commit()
    return _json({"assignment": row.to_dict()}, 201)


@router.patch("/assignments/{assignment_id:int}")
def patch_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_ASSIGN)),
):
    row = update_assignment_status(db, assignment_id, body or {}, current_user)
    db.commit()
    return _json({"assignment": row.to_dict()})


@router.post("/assignments/{assignment_id:int}/reassign")
def reassign_endpoint(
    assignment_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_ASSIGN)),
):
    row = reassign(db, assignment_id, body or {}, current_user)
    db.commit()
    return _json({"assignment": row.to_dict()}, 201)


@router.get("/workers/{worker_id:int}/assignment-context")
def assignment_context(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_READ)),
):
    """Workload + skills when selecting a worker (server-computed)."""
    return _json(worker_context(db, worker_id))


@router.put("/workers/{worker_id:int}/skills")
def put_skills(
    worker_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_HR)),
):
    worker = db.get(Worker, worker_id)
    if not worker:
        return _json({"error": "Worker not found"}, 404)
    data = body or {}
    skills = data.get("skills")
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    set_worker_skills(db, worker, skills if isinstance(skills, list) else [])
    db.commit()
    return _json({"worker": worker.to_dict()})


@router.get("/workers/{worker_id:int}/leave")
def list_leave(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_READ)),
):
    rows = (
        db.query(WorkerLeave)
        .filter(WorkerLeave.worker_id == worker_id)
        .order_by(WorkerLeave.start_date.desc())
        .all()
    )
    return _json({"leave": [r.to_dict() for r in rows]})


@router.post("/workers/{worker_id:int}/leave")
def add_leave(
    worker_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_HR)),
):
    data = dict(body or {})
    data["worker_id"] = worker_id
    row = create_leave(db, data, current_user)
    db.commit()
    return _json({"leave": row.to_dict()}, 201)


@router.post("/work-time")
def add_work_time(
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_ASSIGN + ["technician"])),
):
    """Actual repair time linked to employee + RO — separate from attendance."""
    entry = record_work_time(db, body or {}, current_user)
    db.commit()
    return _json({"entry": entry.to_dict()}, 201)


@router.get("/work-time")
def list_work_time(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_READ)),
):
    q = db.query(WorkTimeEntry)
    if request.query_params.get("worker_id"):
        q = q.filter(WorkTimeEntry.worker_id == int(request.query_params["worker_id"]))
    if request.query_params.get("repair_order_id"):
        q = q.filter(
            WorkTimeEntry.repair_order_id == int(request.query_params["repair_order_id"])
        )
    rows = q.order_by(WorkTimeEntry.id.desc()).limit(200).all()
    return _json({"entries": [r.to_dict() for r in rows]})
