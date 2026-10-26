"""Gate pass / handover endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.foundation.idempotent import idempotent_create
from app.gate_pass import create_gate_pass
from app.models import GatePass, RepairOrder

router = APIRouter(tags=["gate-passes"])


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/repair-orders/{ro_id:int}/gate-pass")
def get_gate_pass(
    ro_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "accountant", "manager", "service_advisor", "inventory_manager"])),
):
    row = (
        db.query(GatePass)
        .filter(GatePass.repair_order_id == ro_id, GatePass.deleted_at.is_(None))
        .first()
    )
    return _json({"gate_pass": row.to_dict() if row else None})


@router.post("/repair-orders/{ro_id:int}/gate-pass")
@idempotent_create
def post_gate_pass(
    ro_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "manager", "service_advisor", "accountant"])),
):
    ro = db.get(RepairOrder, ro_id)
    if not ro:
        return _json({"error": "RO not found"}, 404)
    row = create_gate_pass(db, ro, body or {}, current_user)
    db.commit()
    return _json(row.to_dict(), 201)
