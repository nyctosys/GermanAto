"""Customer deposits (advances) as liability until applied to an issued invoice."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.foundation.audit import audit_write
from app.foundation.overrides import require_audit_reason
from app.models import Attachment, CustomerDeposit, Invoice


def create_deposit(
    db: Session,
    *,
    amount: float,
    visit_id: int | None,
    customer_id: int | None,
    quote_invoice_id: int | None,
    evidence_attachment_id: int | None,
    user,
    branch_id: str | None = None,
) -> CustomerDeposit:
    if amount is None or float(amount) <= 0:
        raise HTTPException(status_code=400, detail="Deposit amount must be > 0")
    if not evidence_attachment_id:
        raise HTTPException(status_code=400, detail="Deposit evidence is required")
    att = db.get(Attachment, evidence_attachment_id)
    if not att:
        raise HTTPException(status_code=400, detail="Evidence attachment not found")
    row = CustomerDeposit(
        visit_id=visit_id,
        customer_id=customer_id,
        quote_invoice_id=quote_invoice_id,
        amount=float(amount),
        status="open",
        evidence_attachment_id=evidence_attachment_id,
        created_by_user=getattr(user, "username", None),
        branch_id=branch_id,
    )
    db.add(row)
    db.flush()
    audit_write(
        db,
        user=user,
        action="CREATE",
        module="customer_deposit",
        reference_id=row.id,
        details="customer deposit (liability)",
        new_value=row.to_dict(),
        reason="customer deposit (liability)",
        branch_id=branch_id,
    )
    return row


def refund_or_adjust(
    db: Session,
    deposit: CustomerDeposit,
    *,
    action: str,
    reason: str | None,
    evidence_attachment_id: int | None,
    user,
) -> CustomerDeposit:
    if deposit.status != "open":
        raise HTTPException(status_code=400, detail=f"Deposit is {deposit.status}, cannot {action}")
    text = require_audit_reason(kind="delete" if action == "refund" else "price_edit", reason=reason)
    if not evidence_attachment_id:
        raise HTTPException(status_code=400, detail="Evidence required for refund/adjust")
    old = deposit.to_dict()
    deposit.status = "refunded" if action == "refund" else "adjusted"
    deposit.reason = text
    deposit.evidence_attachment_id = evidence_attachment_id
    deposit.updated_at = datetime.utcnow()
    audit_write(
        db,
        user=user,
        action=action.upper(),
        module="customer_deposit",
        reference_id=deposit.id,
        details=f"deposit {action}",
        old_value=old,
        new_value=deposit.to_dict(),
        reason=text,
    )
    return deposit


def apply_to_invoice(
    db: Session,
    deposit: CustomerDeposit,
    invoice: Invoice,
    *,
    user,
) -> CustomerDeposit:
    if deposit.status != "open":
        raise HTTPException(status_code=400, detail=f"Deposit is {deposit.status}")
    if (invoice.type_of or "").lower() != "invoice":
        raise HTTPException(status_code=400, detail="Deposit applies only to an issued invoice")
    old = deposit.to_dict()
    deposit.status = "applied"
    deposit.applied_invoice_id = invoice.id
    deposit.updated_at = datetime.utcnow()
    amount = float(deposit.amount or 0)
    invoice.advance = float(invoice.advance or 0) + amount
    from app.invoice_math import calculate_invoice_status, invoice_amount_remaining

    invoice.balance = invoice_amount_remaining(invoice)
    invoice.status = calculate_invoice_status(invoice)
    from app.customer_ar import post_deposit_application

    post_deposit_application(
        db,
        invoice,
        amount=amount,
        username=getattr(user, "username", None),
    )
    audit_write(
        db,
        user=user,
        action="APPLY",
        module="customer_deposit",
        reference_id=deposit.id,
        details=f"applied to invoice #{invoice.id}",
        old_value=old,
        new_value=deposit.to_dict(),
        reason=f"applied to invoice #{invoice.id}",
    )
    return deposit
