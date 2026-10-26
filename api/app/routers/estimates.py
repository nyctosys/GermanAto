"""Estimate (quote) detail, send, revise, stock gaps, advance snapshot."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.estimates import (
    estimate_bundle,
    get_estimate_channels,
    revise_estimate,
    stock_gaps_for_invoice,
)
from app.foundation.idempotent import idempotent_create
from app.foundation.versioning import bump_version, check_version, extract_version
from app.models import Customer, Invoice
from app.quote_approval import mint_approval_token
from app.whatsapp_notifications import whatsapp_notifier

router = APIRouter(tags=["estimates"])

_READ = ["admin", "accountant", "inventory_manager", "service_advisor", "manager", "technician"]
_WRITE = ["admin", "accountant", "service_advisor", "manager"]


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


def _get_quote(db: Session, invoice_id: int) -> Invoice:
    inv = db.get(Invoice, invoice_id)
    if (
        not inv
        or getattr(inv, "deleted_at", None) is not None
        or (inv.type_of or "").lower() not in ("quote", "quotation", "estimate")
    ):
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Estimate not found")
    return inv


@router.get("/estimates/{invoice_id:int}")
def get_estimate(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_READ)),
):
    return _json(estimate_bundle(db, invoice_id))


@router.get("/estimates/{invoice_id:int}/stock-gaps")
def get_stock_gaps(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(_READ)),
):
    inv = _get_quote(db, invoice_id)
    gaps = stock_gaps_for_invoice(db, inv)
    return _json({"gaps": gaps, "count": len(gaps)})


@router.post("/estimates/{invoice_id:int}/revise")
@idempotent_create
def revise(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_WRITE)),
):
    inv = _get_quote(db, invoice_id)
    check_version(inv, extract_version(body or {}))
    clone = revise_estimate(db, inv, current_user)
    bump_version(inv)
    db.commit()
    return _json({"id": clone.id, "parent_quote_id": invoice_id, "estimate": estimate_bundle(db, clone.id)}, 201)


@router.post("/estimates/{invoice_id:int}/send")
@idempotent_create
def send_estimate(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(_WRITE)),
):
    """Send estimate via configured channels (whatsapp / link). Sets approval_state=sent."""
    from app.config import settings

    inv = _get_quote(db, invoice_id)
    data = body or {}
    channels = data.get("channels") or get_estimate_channels(db, branch_id=inv.branch_id)
    channels = [str(c).lower() for c in channels]

    # Consent gates
    cust = db.get(Customer, inv.customer_id) if inv.customer_id else None
    if "whatsapp" in channels and cust and not getattr(cust, "consent_whatsapp", True):
        channels = [c for c in channels if c != "whatsapp"]
    if "sms" in channels and cust and not getattr(cust, "consent_sms", True):
        channels = [c for c in channels if c != "sms"]

    token_row = mint_approval_token(
        db, inv, created_by=getattr(current_user, "username", None)
    )
    base = data.get("public_base_url") or getattr(settings, "public_web_url", None) or "http://localhost:5173"
    link = f"{base.rstrip('/')}/approve/{token_row.token}"

    sent = []
    if "whatsapp" in channels:
        try:
            whatsapp_notifier.send_invoice_notification(
                {
                    "id": inv.id,
                    "customer_name": inv.customer_name,
                    "customer_phone": inv.customer_phone,
                    "net_total": inv.net_total,
                    "type_of": "quote",
                    "approval_link": link,
                    "required_advance": getattr(inv, "required_advance", None),
                }
            )
            sent.append("whatsapp")
        except Exception:
            pass
    if "link" in channels or "sms" in channels:
        sent.append("link")

    inv.approval_state = "sent"
    bump_version(inv)
    db.commit()
    return _json(
        {
            "token": token_row.token,
            "approval_url": link,
            "channels_requested": channels,
            "channels_sent": sent,
            "approval_state": inv.approval_state,
            "message": "Estimate sent for customer approval (not revenue)",
        }
    )

