"""Labour code catalogue CRUD."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.foundation.idempotent import idempotent_create
from app.foundation.versioning import bump_version, check_version, extract_version
from app.models import LabourCode

router = APIRouter(tags=["labour-codes"])


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/labour-codes")
def list_labour_codes(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "accountant", "inventory_manager", "service_advisor", "technician", "manager"])),
    active_only: bool = True,
):
    q = db.query(LabourCode).filter(LabourCode.deleted_at.is_(None))
    if active_only:
        q = q.filter(LabourCode.is_active.is_(True))
    rows = q.order_by(LabourCode.code).all()
    return _json([r.to_dict() for r in rows])


@router.post("/labour-codes")
@idempotent_create
def create_labour_code(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "manager", "service_advisor"])),
):
    data = body or {}
    code = str(data.get("code") or "").strip().upper()
    if not code:
        return _json({"error": "code is required"}, 400)
    if db.query(LabourCode).filter(LabourCode.code == code, LabourCode.deleted_at.is_(None)).first():
        return _json({"error": "code already exists"}, 400)
    rate = float(data.get("rate") or 0)
    hours = float(data.get("standard_hours") or 1)
    if rate < 0 or hours < 0:
        return _json({"error": "rate/hours cannot be negative"}, 400)
    row = LabourCode(
        code=code,
        description=str(data.get("description") or "").strip() or code,
        standard_hours=hours,
        rate=rate,
        category=str(data.get("category") or "general").strip(),
        is_active=bool(data.get("is_active", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _json(row.to_dict(), 201)


@router.put("/labour-codes/{code_id:int}")
def update_labour_code(
    code_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "manager", "service_advisor"])),
):
    row = db.get(LabourCode, code_id)
    if not row or row.deleted_at is not None:
        return _json({"error": "Not found"}, 404)
    data = body or {}
    check_version(row, extract_version(data))
    for field in ("description", "category"):
        if field in data:
            setattr(row, field, str(data[field]).strip())
    if "standard_hours" in data:
        row.standard_hours = float(data["standard_hours"])
    if "rate" in data:
        row.rate = float(data["rate"])
    if "is_active" in data:
        row.is_active = bool(data["is_active"])
    if row.rate < 0 or row.standard_hours < 0:
        return _json({"error": "rate/hours cannot be negative"}, 400)
    bump_version(row)
    db.commit()
    return _json(row.to_dict())


@router.delete("/labour-codes/{code_id:int}")
def delete_labour_code(
    code_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "manager"])),
):
    from app.foundation.overrides import require_audit_reason
    from datetime import datetime

    row = db.get(LabourCode, code_id)
    if not row or row.deleted_at is not None:
        return _json({"error": "Not found"}, 404)
    require_audit_reason(kind="delete")
    row.deleted_at = datetime.utcnow()
    db.commit()
    return _json({"message": "deleted"})
