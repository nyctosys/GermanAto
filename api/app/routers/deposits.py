"""Customer deposit (advance liability) endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deposits import apply_to_invoice, create_deposit, refund_or_adjust
from app.deps import require_roles
from app.foundation.idempotent import idempotent_create
from app.models import CustomerDeposit, Invoice

router = APIRouter(tags=["deposits"])


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/deposits")
def list_deposits(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "accountant", "manager", "service_advisor"])),
    visit_id: int | None = None,
):
    q = db.query(CustomerDeposit).filter(CustomerDeposit.deleted_at.is_(None))
    if visit_id:
        q = q.filter(CustomerDeposit.visit_id == visit_id)
    return _json([r.to_dict() for r in q.order_by(CustomerDeposit.id.desc()).limit(200)])


@router.post("/deposits")
@idempotent_create
def create(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "accountant", "manager", "service_advisor"])),
):
    data = body or {}
    row = create_deposit(
        db,
        amount=float(data.get("amount") or 0),
        visit_id=data.get("visit_id"),
        customer_id=data.get("customer_id"),
        quote_invoice_id=data.get("quote_invoice_id"),
        evidence_attachment_id=data.get("evidence_attachment_id"),
        user=current_user,
        branch_id=data.get("branch_id"),
    )
    db.commit()
    return _json(row.to_dict(), 201)


@router.post("/deposits/{deposit_id:int}/refund")
def refund(
    deposit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "accountant", "manager"])),
):
    row = db.get(CustomerDeposit, deposit_id)
    if not row:
        return _json({"error": "Not found"}, 404)
    data = body or {}
    refund_or_adjust(
        db,
        row,
        action="refund",
        reason=data.get("reason"),
        evidence_attachment_id=data.get("evidence_attachment_id"),
        user=current_user,
    )
    db.commit()
    return _json(row.to_dict())


@router.post("/deposits/{deposit_id:int}/adjust")
def adjust(
    deposit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "accountant", "manager"])),
):
    row = db.get(CustomerDeposit, deposit_id)
    if not row:
        return _json({"error": "Not found"}, 404)
    data = body or {}
    refund_or_adjust(
        db,
        row,
        action="adjust",
        reason=data.get("reason"),
        evidence_attachment_id=data.get("evidence_attachment_id"),
        user=current_user,
    )
    db.commit()
    return _json(row.to_dict())


@router.post("/deposits/{deposit_id:int}/apply")
def apply(
    deposit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin", "accountant", "manager"])),
):
    row = db.get(CustomerDeposit, deposit_id)
    if not row:
        return _json({"error": "Not found"}, 404)
    invoice_id = (body or {}).get("invoice_id")
    invoice = db.get(Invoice, int(invoice_id)) if invoice_id else None
    if not invoice:
        return _json({"error": "invoice_id required"}, 400)
    apply_to_invoice(db, row, invoice, user=current_user)
    db.commit()
    return _json(row.to_dict())
