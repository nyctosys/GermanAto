"""Technician repair execution API — assigned jobs, time, parts, faults, QC submit."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.foundation.attachments import save_evidence
from app.foundation.idempotent import idempotent_create
from app import repair_execution as rex

router = APIRouter(tags=["repair-execution"])

_TECH = ["admin", "manager", "service_advisor", "technician", "accountant"]
_STOCK = ["admin", "manager", "store_keeper", "inventory_manager", "technician", "service_advisor"]


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/repair-execution/jobs")
def list_jobs(
    worker_id: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_TECH)),
):
    jobs = rex.list_assigned_jobs(db, worker_id=worker_id)
    return _json({"jobs": jobs, "payroll_note": (
        "Repair time is for job cost only; payroll uses attendance hours separately."
    )})


@router.get("/repair-orders/{ro_id:int}/execution")
def get_execution(
    ro_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_TECH + ["store_keeper", "inventory_manager"])),
):
    return _json(rex.execution_board(db, ro_id))


@router.post("/repair-orders/{ro_id:int}/execution/labour/{labour_id:int}/start")
@idempotent_create
def start_labour(
    ro_id: int,
    labour_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        data = body or {}
        result = rex.start_labour(
            db, ro, labour_id, current_user, worker_id=data.get("worker_id")
        )
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/labour/{labour_id:int}/pause")
def pause_labour(
    ro_id: int,
    labour_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        result = rex.pause_labour(db, ro, labour_id, current_user)
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/labour/{labour_id:int}/resume")
@idempotent_create
def resume_labour(
    ro_id: int,
    labour_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        data = body or {}
        result = rex.resume_labour(
            db, ro, labour_id, current_user, worker_id=data.get("worker_id")
        )
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/labour/{labour_id:int}/time")
@idempotent_create
def record_time(
    ro_id: int,
    labour_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        data = body or {}
        hours = float(data.get("hours") or 0)
        result = rex.record_manual_hours(
            db,
            ro,
            labour_id,
            current_user,
            hours=hours,
            notes=data.get("notes"),
            replace=bool(data.get("replace")),
        )
        db.commit()
        return _json(result, 201)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/labour/{labour_id:int}/complete")
def complete_labour(
    ro_id: int,
    labour_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        result = rex.complete_labour(
            db, ro, labour_id, current_user, notes=(body or {}).get("notes")
        )
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/labour/{labour_id:int}/notes")
def labour_note(
    ro_id: int,
    labour_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        result = rex.add_labour_note(
            db, ro, labour_id, current_user, (body or {}).get("note") or ""
        )
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/parts/request")
@idempotent_create
def request_parts(
    ro_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        result = rex.request_parts(db, ro, body or {}, current_user)
        db.commit()
        return _json(result, 201)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/parts/{part_id:int}/issue")
@idempotent_create
def issue_parts(
    ro_id: int,
    part_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_STOCK)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        data = body or {}
        result = rex.issue_parts(
            db,
            ro,
            part_id,
            current_user,
            qty=data.get("qty") or data.get("quantity"),
            from_reserve=data.get("from_reserve"),
        )
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/parts/{part_id:int}/return")
@idempotent_create
def return_parts(
    ro_id: int,
    part_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_STOCK)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        data = body or {}
        result = rex.return_parts(
            db, ro, part_id, current_user, qty=data.get("qty") or data.get("quantity")
        )
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/faults")
@idempotent_create
def record_fault(
    ro_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        result = rex.record_fault(db, ro, body or {}, current_user)
        db.commit()
        return _json(result, 201)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.patch("/repair-orders/{ro_id:int}/execution/faults/{fault_id:int}")
def patch_fault(
    ro_id: int,
    fault_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        result = rex.update_fault(db, ro, fault_id, body or {}, current_user)
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.delete("/repair-orders/{ro_id:int}/execution/faults/{fault_id:int}")
def remove_fault(
    ro_id: int,
    fault_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        result = rex.delete_fault(db, ro, fault_id, current_user)
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/variations/{var_id:int}/promote")
@idempotent_create
def promote_variation(
    ro_id: int,
    var_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        result = rex.promote_variation(db, ro, var_id, current_user)
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/attachments")
async def upload_attachment(
    ro_id: int,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        saved = save_evidence(
            db,
            file,
            entity_type="repair_order",
            entity_id=ro.id,
            branch_id=ro.branch_id,
            uploaded_by=getattr(current_user, "username", None),
            notes="Repair execution photo/note",
        )
        if not saved:
            return _json({"error": "Upload failed"}, 400)
        db.commit()
        return _json({"attachment": saved}, 201)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/notes")
def update_notes(
    ro_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        result = rex.update_ro_notes(db, ro, current_user, (body or {}).get("notes") or "")
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.post("/repair-orders/{ro_id:int}/execution/submit-inspection")
def submit_inspection(
    ro_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_TECH)),
):
    try:
        ro = rex.get_ro(db, ro_id)
        result = rex.submit_for_inspection(
            db, ro, current_user, notes=(body or {}).get("notes")
        )
        db.commit()
        return _json(result)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)
