"""QC sign-off endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.foundation.idempotent import idempotent_create
from app.models import QcSignoff, RepairOrder
from app.qc import create_qc_signoff

router = APIRouter(tags=["qc"])


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/repair-orders/{ro_id:int}/qc")
def get_qc(
    ro_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "accountant", "manager", "technician", "service_advisor", "inventory_manager"])),
):
    row = (
        db.query(QcSignoff)
        .filter(QcSignoff.repair_order_id == ro_id, QcSignoff.deleted_at.is_(None))
        .order_by(QcSignoff.id.desc())
        .first()
    )
    if not row:
        return _json({"qc": None})
    return _json({"qc": row.to_dict()})


@router.post("/repair-orders/{ro_id:int}/qc")
@idempotent_create
def post_qc(
    ro_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "manager", "inventory_manager"])),
):
    ro = db.get(RepairOrder, ro_id)
    if not ro:
        return _json({"error": "RO not found"}, 404)
    row = create_qc_signoff(db, ro, body or {}, current_user)
    db.commit()
    return _json(row.to_dict(), 201)
