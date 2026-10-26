"""Variation request endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import require_roles
from app.foundation.idempotent import idempotent_create
from app.models import RepairOrder, Variation
from app.quote_approval import mint_approval_token
from app.variations import create_variation, send_variation_quote
from app.whatsapp_notifications import whatsapp_notifier

router = APIRouter(tags=["variations"])


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/repair-orders/{ro_id:int}/variations")
def list_variations(
    ro_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "accountant", "inventory_manager", "technician", "manager", "service_advisor"])),
):
    rows = (
        db.query(Variation)
        .options(joinedload(Variation.lines))
        .filter(Variation.repair_order_id == ro_id, Variation.deleted_at.is_(None))
        .all()
    )
    return _json([r.to_dict() for r in rows])


@router.post("/repair-orders/{ro_id:int}/variations")
@idempotent_create
def create(
    ro_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "technician", "manager", "service_advisor", "inventory_manager"])),
):
    ro = db.get(RepairOrder, ro_id)
    if not ro:
        return _json({"error": "RO not found"}, 404)
    var = create_variation(db, ro, body or {}, current_user)
    db.commit()
    return _json(var.to_dict(), 201)


@router.post("/variations/{variation_id:int}/send")
def send(
    variation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(
        require_roles(["admin", "manager", "service_advisor", "accountant", "technician"])
    ),
):
    from app.config import settings

    var = (
        db.query(Variation)
        .options(joinedload(Variation.lines))
        .filter(Variation.id == variation_id)
        .first()
    )
    if not var:
        return _json({"error": "Not found"}, 404)
    ro = db.get(RepairOrder, var.repair_order_id)
    invoice = send_variation_quote(db, var, ro, current_user)
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
    return _json({"invoice_id": invoice.id, "approval_url": link, "token": token_row.token})
