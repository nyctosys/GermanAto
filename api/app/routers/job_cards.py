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
from app.job_cards import build_quote_from_job_card, create_job_card, get_job_card, replace_lines
from app.models import JobCard
from app.quote_approval import mint_approval_token
from app.whatsapp_notifications import whatsapp_notifier

router = APIRouter(tags=["job-cards"])


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/job-cards")
def list_job_cards(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "accountant", "inventory_manager", "service_advisor", "manager", "technician"])),
):
    rows = (
        db.query(JobCard)
        .filter(JobCard.deleted_at.is_(None))
        .order_by(JobCard.id.desc())
        .limit(200)
        .all()
    )
    return _json([r.to_dict(include_lines=False) for r in rows])


@router.get("/job-cards/{job_card_id:int}")
def get_one(
    job_card_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "accountant", "inventory_manager", "service_advisor", "manager", "technician"])),
):
    return _json(get_job_card(db, job_card_id).to_dict())


@router.post("/job-cards")
@idempotent_create
def create(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "accountant", "service_advisor", "manager"])),
):
    try:
        card = create_job_card(db, body or {}, current_user)
        db.commit()
        return _json(card.to_dict(), 201)
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
    current_user=Depends(require_roles(["admin", "accountant", "service_advisor", "manager"])),
):
    card = get_job_card(db, job_card_id)
    data = body or {}
    check_version(card, extract_version(data))
    for f in ("customer_name", "customer_phone", "customer_reg_no", "customer_made", "notes", "status"):
        if f in data:
            setattr(card, f, data[f])
    if "lines" in data:
        replace_lines(db, card, data["lines"] or [])
    bump_version(card)
    db.commit()
    return _json(get_job_card(db, job_card_id).to_dict())


@router.post("/job-cards/{job_card_id:int}/quote")
@idempotent_create
def create_quote(
    job_card_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "accountant", "service_advisor", "manager"])),
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
    current_user=Depends(require_roles(["admin", "accountant", "service_advisor", "manager"])),
):
    from app.models import Invoice
    from app.config import settings

    invoice = db.get(Invoice, invoice_id)
    if not invoice or (invoice.type_of or "").lower() != "quote":
        return _json({"error": "Quote not found"}, 404)
    token_row = mint_approval_token(
        db, invoice, created_by=getattr(current_user, "username", None)
    )
    base = (body or {}).get("public_base_url") or getattr(settings, "public_web_url", None) or "http://localhost:5173"
    link = f"{base.rstrip('/')}/approve/{token_row.token}"
    try:
        whatsapp_notifier.send_invoice_notification(
            {
                "id": invoice.id,
                "customer_name": invoice.customer_name,
                "customer_phone": invoice.customer_phone,
                "net_total": invoice.net_total,
                "type_of": "quote",
                "approval_link": link,
            }
        )
    except Exception:
        pass
    db.commit()
    return _json({"token": token_row.token, "approval_url": link})
