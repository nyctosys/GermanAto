"""Tokenized public quote/variation line approval + reserve on full approval."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.foundation.audit import audit_write
from app.log_utils import save_data_url
from app.models import (
    ApprovalToken,
    Attachment,
    Invoice,
    InvoiceItem,
    InvoiceLabour,
    QuoteLineApproval,
    Variation,
    VariationLine,
)
from app.parts_flow import reserve_for_quote


def mint_approval_token(
    db: Session,
    invoice: Invoice,
    *,
    created_by: str | None,
    days_valid: int = 14,
) -> ApprovalToken:
    token = secrets.token_urlsafe(32)
    row = ApprovalToken(
        token=token,
        invoice_id=invoice.id,
        expires_at=datetime.utcnow() + timedelta(days=days_valid),
        created_by=created_by,
        branch_id=invoice.branch_id,
    )
    db.add(row)
    db.flush()
    return row


def resolve_token(db: Session, token: str) -> tuple[ApprovalToken, Invoice]:
    row = db.query(ApprovalToken).filter(ApprovalToken.token == token).first()
    if not row or row.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Approval link invalid")
    if row.expires_at and row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Approval link expired")
    invoice = db.get(Invoice, row.invoice_id)
    if not invoice or invoice.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return row, invoice


def public_quote_payload(invoice: Invoice) -> dict:
    return {
        "invoice_id": invoice.id,
        "type_of": invoice.type_of,
        "is_variation": bool(invoice.is_variation),
        "customer_name": invoice.customer_name,
        "customer_reg_no": invoice.customer_reg_no,
        "net_total": invoice.net_total,
        "discount": invoice.discount,
        "items": [
            {
                "id": i.id,
                "kind": "item",
                "product_name": i.product_name,
                "part_number": i.part_number,
                "quantity": i.quantity,
                "price": i.price,
                "proposed_price": i.proposed_price,
                "approval_status": i.approval_status or "pending",
            }
            for i in (invoice.items or [])
        ],
        "labours": [
            {
                "id": l.id,
                "kind": "labour",
                "description": l.description,
                "price": l.price,
                "proposed_price": l.proposed_price,
                "std_hours": l.std_hours,
                "approval_status": l.approval_status or "pending",
            }
            for l in (invoice.labours or [])
        ],
    }


def _attach_media(
    db: Session,
    data_url: str | None,
    *,
    invoice_id: int,
    branch_id: str | None,
) -> Attachment | None:
    path = save_data_url(data_url, prefix="approval")
    if not path:
        return None
    row = Attachment(
        branch_id=branch_id or "a1b2c3d4",
        entity_type="quote_line_approval",
        entity_id=invoice_id,
        file_path=path,
        original_name="approval_media.png",
        content_type="image/png",
        notes="customer approval evidence",
    )
    db.add(row)
    db.flush()
    return row


def apply_line_decisions(
    db: Session,
    invoice: Invoice,
    decisions: list[dict],
    *,
    token: str,
    client_ip: str | None,
    user=None,
) -> dict:
    """decisions: [{kind: item|labour, id, decision: approved|rejected, media_data_url?, notes?}]"""
    if not decisions:
        raise HTTPException(status_code=400, detail="No line decisions provided")

    for d in decisions:
        kind = (d.get("kind") or "").lower()
        line_id = int(d.get("id"))
        decision = (d.get("decision") or "").lower()
        if decision not in ("approved", "rejected"):
            raise HTTPException(status_code=400, detail=f"Invalid decision: {decision}")
        media = _attach_media(
            db, d.get("media_data_url"), invoice_id=invoice.id, branch_id=invoice.branch_id
        )
        if kind == "item":
            line = db.get(InvoiceItem, line_id)
            if not line or line.invoice_id != invoice.id:
                raise HTTPException(status_code=404, detail=f"Item {line_id} not found")
            line.approval_status = decision
        elif kind == "labour":
            line = db.get(InvoiceLabour, line_id)
            if not line or line.invoice_id != invoice.id:
                raise HTTPException(status_code=404, detail=f"Labour {line_id} not found")
            line.approval_status = decision
        else:
            raise HTTPException(status_code=400, detail=f"Invalid kind: {kind}")

        evidence = QuoteLineApproval(
            invoice_id=invoice.id,
            line_kind=kind,
            line_id=line_id,
            decision=decision,
            decided_at=datetime.utcnow(),
            client_ip=client_ip,
            token=token,
            media_attachment_id=media.id if media else None,
            notes=d.get("notes"),
            branch_id=invoice.branch_id,
        )
        db.add(evidence)

        # Mirror onto variation lines when this is a variation quote
        if invoice.is_variation and invoice.repair_order_id:
            _sync_variation_line(db, invoice, kind, line_id, decision)

    db.flush()

    from app.estimates import rollup_approval_state

    invoice.approval_state = rollup_approval_state(invoice)

    # If any approved parts → reserve
    has_approved_parts = any(
        (i.approval_status or "") == "approved" and i.inventory_id for i in (invoice.items or [])
    )
    if has_approved_parts:
        reserve_for_quote(db, invoice, created_by=getattr(user, "id", None))

    # Update parent variation status
    if invoice.is_variation:
        var = (
            db.query(Variation)
            .filter(Variation.quote_invoice_id == invoice.id)
            .first()
        )
        if var:
            statuses = [ln.approval_status for ln in (var.lines or [])]
            if statuses and all(s == "approved" for s in statuses):
                var.status = "approved"
            elif statuses and all(s == "rejected" for s in statuses):
                var.status = "rejected"
            elif any(s == "approved" for s in statuses):
                var.status = "partially_approved"

    audit_write(
        db,
        user=user,
        action="LINE_APPROVAL",
        module="quotes",
        reference_id=invoice.id,
        details=f"{len(decisions)} line decisions via public token",
        new_value=public_quote_payload(invoice),
        reason="customer line-wise approval",
    )
    return public_quote_payload(invoice)


def _sync_variation_line(
    db: Session, invoice: Invoice, kind: str, invoice_line_id: int, decision: str
) -> None:
    var = db.query(Variation).filter(Variation.quote_invoice_id == invoice.id).first()
    if not var:
        return
    # Match by description loosely via invoice line
    if kind == "item":
        src = db.get(InvoiceItem, invoice_line_id)
        if not src:
            return
        for vl in var.lines or []:
            if vl.line_type == "part" and vl.description == src.product_name:
                vl.approval_status = decision
    else:
        src = db.get(InvoiceLabour, invoice_line_id)
        if not src:
            return
        for vl in var.lines or []:
            if vl.line_type == "labour" and vl.description == src.description:
                vl.approval_status = decision
