"""Next-action status for job cards and repair orders."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.pipeline import next_action

router = APIRouter(tags=["pipeline"])


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/pipeline/next-action")
def get_next_action(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_roles(
            ["admin", "accountant", "manager", "service_advisor", "inventory_manager", "technician"]
        )
    ),
    job_card_id: int | None = None,
    repair_order_id: int | None = None,
):
    return _json(next_action(db, job_card_id=job_card_id, repair_order_id=repair_order_id))
