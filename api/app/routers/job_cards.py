"""Job card endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.foundation.idempotent import idempotent_create
from app.foundation.versioning import bump_version, check_version, extract_version
from app.job_cards import (
    _enrich,
    build_quote_from_job_card,
    create_job_card,
    get_job_card,
    list_job_cards,
    update_job_card,
)
router = APIRouter(tags=["job-cards"])

_READ = ["admin", "accountant", "inventory_manager", "service_advisor", "manager", "technician"]
_WRITE = ["admin", "accountant", "service_advisor", "manager"]


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/job-cards")
def list_cards(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_READ)),
):
    q = (request.query_params.get("q") or request.query_params.get("keyword") or "").strip()
    status = (request.query_params.get("status") or "").strip() or None
    limit = int(request.query_params.get("limit") or 200)
    rows = list_job_cards(db, q=q or None, status=status, limit=limit)
    return _json([_enrich(r, db) for r in rows])


@router.get("/job-cards/{job_card_id:int}")
def get_one(
    job_card_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_READ)),
):
    return _json(_enrich(get_job_card(db, job_card_id), db))


@router.post("/job-cards")
@idempotent_create
def create(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_WRITE)),
):
    try:
        card = create_job_card(db, body or {}, current_user)
        db.commit()
        return _json(_enrich(card, db), 201)
    except Exception as e:
        db.rollback()
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            raise
        return _json({"error": str(e)}, 400)


@router.put("/job-cards/{job_card_id:int}")
def update(
    job_card_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_WRITE)),
):
    card = get_job_card(db, job_card_id)
    data = body or {}
    check_version(card, extract_version(data))
    update_job_card(db, card, data, current_user)
    bump_version(card)
    db.commit()
    return _json(_enrich(get_job_card(db, job_card_id), db))


@router.post("/job-cards/{job_card_id:int}/assign-worker")
def assign_worker(
    job_card_id: int,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_WRITE)),
):
    from app.assignments import create_assignment

    card = get_job_card(db, job_card_id)
    data = body or {}
    check_version(card, extract_version(data))
    worker_id = data.get("worker_id")
    assignment = None
    if worker_id:
        assignment = create_assignment(
            db,
            {
                "worker_id": worker_id,
                "job_card_id": job_card_id,
                "team_name": data.get("team_name", card.team_name),
                "priority": data.get("priority") or getattr(card, "priority", None) or "normal",
                "estimated_start_at": data.get("estimated_start_at"),
                "estimated_completion_at": data.get("estimated_completion_at"),
                "deadline_at": data.get("deadline_at")
                or getattr(card, "expected_completion_at", None),
                "notes": data.get("notes"),
                "override_reason": data.get("override_reason") or data.get("reason"),
            },
            current_user,
        )
    else:
        update_job_card(
            db,
            card,
            {
                "worker_id": None,
                "team_name": data.get("team_name", card.team_name),
                "reason": data.get("reason") or "Clear worker",
            },
            current_user,
        )
    bump_version(card)
    db.commit()
    out = _enrich(get_job_card(db, job_card_id), db)
    if assignment:
        out["assignment"] = assignment.to_dict()
    return _json(out)


@router.post("/job-cards/{job_card_id:int}/quote")
@idempotent_create
def create_quote(
    job_card_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_WRITE)),
):
    card = get_job_card(db, job_card_id)
    invoice = build_quote_from_job_card(db, card, body or {}, current_user)
    db.commit()
    return _json({"invoice_id": invoice.id, "quote": {"id": invoice.id, "net_total": invoice.net_total}}, 201)


@router.post("/quotes/{invoice_id:int}/send-approval")
def send_approval(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_WRITE)),
):
    """Delegate to estimate send (channels + approval_state=sent)."""
    from app.routers.estimates import send_estimate

    return send_estimate(invoice_id, request, db, body, current_user)
