"""Estimates (quotes): advance policy, stock gaps, lifecycle, revise, money snapshot.

Estimates are not earned revenue. Customer advances are CustomerDeposit liabilities
until applied to an issued invoice.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.foundation.audit import audit_write
from app.foundation.overrides import require_audit_reason
from app.foundation.settings import get_setting
from app.invoice_math import invoice_amount_due
from app.models import (
    CustomerDeposit,
    Inventory,
    Invoice,
    InvoiceItem,
    InvoiceLabour,
    JobCard,
)

SETTING_ADVANCE_POLICY = "advance_policy"
SETTING_ESTIMATE_CHANNELS = "estimate_notify_channels"
SETTING_VARIATION_REQUIRES_APPROVAL = "variation_requires_approval"

DEFAULT_ADVANCE_POLICY: dict[str, Any] = {
    "mode": "percent",  # none | fixed | percent | full | custom
    "fixed_amount": 0.0,
    "percent": 50.0,
    "allow_authorized_custom": True,
}

DEFAULT_CHANNELS = ["whatsapp"]  # whatsapp | sms | link

APPROVAL_STATES = {
    "draft",
    "sent",
    "approved",
    "rejected",
    "revised",
    "partially_approved",
}


def get_advance_policy(db: Session, *, branch_id: str | None = None) -> dict[str, Any]:
    raw = get_setting(db, SETTING_ADVANCE_POLICY, branch_id=branch_id)
    if not isinstance(raw, dict):
        return dict(DEFAULT_ADVANCE_POLICY)
    out = dict(DEFAULT_ADVANCE_POLICY)
    out.update(raw)
    return out


def get_estimate_channels(db: Session, *, branch_id: str | None = None) -> list[str]:
    raw = get_setting(db, SETTING_ESTIMATE_CHANNELS, branch_id=branch_id)
    if isinstance(raw, list) and raw:
        return [str(c).lower() for c in raw]
    return list(DEFAULT_CHANNELS)


def required_advance(
    final_amount: float,
    policy: dict[str, Any] | None,
    *,
    custom_amount: float | None = None,
    authorized: bool = False,
) -> float:
    """Compute required advance. Example: 50% of 100_000 → 50_000."""
    final = round(float(final_amount or 0), 2)
    if final <= 0:
        return 0.0
    pol = policy or DEFAULT_ADVANCE_POLICY
    mode = str(pol.get("mode") or "none").lower()
    if mode == "none":
        return 0.0
    if mode == "full":
        return final
    if mode == "fixed":
        return round(min(final, float(pol.get("fixed_amount") or 0)), 2)
    if mode == "percent":
        pct = float(pol.get("percent") or 0)
        return round(final * pct / 100.0, 2)
    if mode == "custom":
        if custom_amount is None:
            raise HTTPException(
                status_code=400,
                detail="Custom advance amount is required for this advance policy",
            )
        if not authorized and not pol.get("allow_authorized_custom", True):
            raise HTTPException(status_code=403, detail="Custom advance not authorized")
        amt = round(float(custom_amount), 2)
        if amt < 0 or amt > final:
            raise HTTPException(
                status_code=400,
                detail="Custom advance must be between 0 and final estimate",
            )
        if not authorized:
            require_audit_reason(kind="price_edit", reason="authorized custom advance")
        return amt
    raise HTTPException(status_code=400, detail=f"Unknown advance policy mode: {mode}")


def estimate_final_amount(invoice: Invoice) -> float:
    return round(float(invoice_amount_due(invoice)), 2)


def deposits_for_quote(db: Session, quote_id: int) -> list[CustomerDeposit]:
    return (
        db.query(CustomerDeposit)
        .filter(
            CustomerDeposit.quote_invoice_id == quote_id,
            CustomerDeposit.deleted_at.is_(None),
        )
        .order_by(CustomerDeposit.id.desc())
        .all()
    )


def advance_received(db: Session, quote_id: int) -> float:
    total = 0.0
    for d in deposits_for_quote(db, quote_id):
        if (d.status or "") in ("open", "applied"):
            total += float(d.amount or 0)
    return round(total, 2)


def stock_gaps_for_invoice(db: Session, invoice: Invoice) -> list[dict]:
    """Parts needed vs available (on_hand - reserved)."""
    gaps = []
    for item in invoice.items or []:
        if not item.inventory_id:
            continue
        inv = db.get(Inventory, item.inventory_id)
        if not inv or getattr(inv, "deleted_at", None) is not None:
            gaps.append(
                {
                    "inventory_id": item.inventory_id,
                    "product_name": item.product_name,
                    "part_number": item.part_number,
                    "needed": int(item.quantity or 0),
                    "available": 0,
                    "missing": int(item.quantity or 0),
                    "missing_part": True,
                }
            )
            continue
        available = int(inv.available)
        needed = int(item.quantity or 0)
        missing = max(0, needed - available)
        if missing > 0:
            gaps.append(
                {
                    "inventory_id": inv.id,
                    "product_name": inv.name or item.product_name,
                    "part_number": inv.part_number or item.part_number,
                    "needed": needed,
                    "available": available,
                    "missing": missing,
                    "missing_part": True,
                }
            )
    return gaps


def rollup_approval_state(invoice: Invoice) -> str:
    statuses = [(i.approval_status or "pending").lower() for i in (invoice.items or [])] + [
        (l.approval_status or "pending").lower() for l in (invoice.labours or [])
    ]
    if not statuses:
        return getattr(invoice, "approval_state", None) or "draft"
    if all(s == "approved" for s in statuses):
        return "approved"
    if all(s == "rejected" for s in statuses):
        return "rejected"
    if any(s == "approved" for s in statuses) and any(s == "rejected" for s in statuses):
        return "partially_approved"
    if any(s in ("approved", "rejected") for s in statuses):
        return "partially_approved"
    # still all pending after send
    if (getattr(invoice, "approval_state", None) or "") == "sent":
        return "sent"
    return getattr(invoice, "approval_state", None) or "draft"


def apply_estimate_money_fields(
    db: Session,
    invoice: Invoice,
    *,
    policy: dict[str, Any] | None = None,
    custom_advance: float | None = None,
    authorized_custom: bool = False,
) -> Invoice:
    pol = policy or get_advance_policy(db, branch_id=invoice.branch_id)
    final = estimate_final_amount(invoice)
    mode = str(pol.get("mode") or "none").lower()
    if mode == "custom" and custom_advance is None:
        # Snapshot without staff override: use configured percent as guidance.
        req = required_advance(final, {**pol, "mode": "percent", "percent": pol.get("percent") or 50})
    else:
        req = required_advance(
            final,
            pol,
            custom_amount=custom_advance,
            authorized=authorized_custom,
        )
    invoice.required_advance = req
    invoice.advance_policy_mode = mode
    invoice.advance_policy_value = float(
        pol.get("percent") if mode == "percent" else pol.get("fixed_amount") or 0
    )
    return invoice


def estimate_bundle(db: Session, invoice_id: int) -> dict:
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.items), joinedload(Invoice.labours))
        .filter(Invoice.id == invoice_id, Invoice.deleted_at.is_(None))
        .first()
    )
    if not invoice or (invoice.type_of or "").lower() not in ("quote", "quotation", "estimate"):
        raise HTTPException(status_code=404, detail="Estimate not found")

    final = estimate_final_amount(invoice)
    received = advance_received(db, invoice.id)
    required = float(getattr(invoice, "required_advance", None) or 0)
    if not required:
        try:
            apply_estimate_money_fields(db, invoice)
            required = float(invoice.required_advance or 0)
        except Exception:
            required = 0.0
    remaining = round(max(0.0, required - received), 2)
    gaps = stock_gaps_for_invoice(db, invoice)
    deposits = [d.to_dict() for d in deposits_for_quote(db, invoice.id)]

    duration = getattr(invoice, "expected_duration_hours", None)
    if duration is None:
        duration = sum(float(l.std_hours or 0) for l in (invoice.labours or []))

    return {
        "estimate": {
            "id": invoice.id,
            "document_no": invoice.document_no,
            "type_of": invoice.type_of,
            "approval_state": getattr(invoice, "approval_state", None) or "draft",
            "status": invoice.status,
            "customer_id": invoice.customer_id,
            "car_id": invoice.car_id,
            "customer_name": invoice.customer_name,
            "customer_phone": invoice.customer_phone,
            "customer_reg_no": invoice.customer_reg_no,
            "customer_made": invoice.customer_made,
            "job_card_id": invoice.job_card_id,
            "visit_id": invoice.visit_id,
            "parent_quote_id": invoice.parent_quote_id,
            "is_variation": bool(invoice.is_variation),
            "net_total": invoice.net_total,
            "discount": invoice.discount,
            "include_tax": invoice.include_tax,
            "tax_amount": invoice.tax_amount,
            "final_estimate": final,
            "required_advance": required,
            "advance_received": received,
            "remaining_advance_due": remaining,
            "advance_policy_mode": getattr(invoice, "advance_policy_mode", None),
            "advance_policy_value": getattr(invoice, "advance_policy_value", None),
            "expected_duration_hours": duration,
            "expected_completion_at": (
                invoice.expected_completion_at.strftime("%Y-%m-%d %H:%M:%S")
                if getattr(invoice, "expected_completion_at", None)
                else None
            ),
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
            "version": invoice.version,
            "items": [
                {
                    "id": i.id,
                    "product_name": i.product_name,
                    "part_number": i.part_number,
                    "quantity": i.quantity,
                    "price": i.price,
                    "line_total": round(float(i.price or 0) * int(i.quantity or 0), 2),
                    "inventory_id": i.inventory_id,
                    "approval_status": i.approval_status,
                }
                for i in (invoice.items or [])
            ],
            "labours": [
                {
                    "id": l.id,
                    "description": l.description,
                    "price": l.price,
                    "std_hours": l.std_hours,
                    "labour_code_id": l.labour_code_id,
                    "approval_status": l.approval_status,
                }
                for l in (invoice.labours or [])
            ],
        },
        "money": {
            "subtotal": invoice.net_total,
            "discount": invoice.discount,
            "tax": invoice.tax_amount if invoice.include_tax else 0,
            "final_estimate": final,
            "required_advance": required,
            "advance_received": received,
            "remaining_advance_due": remaining,
            "is_revenue": False,
            "advances_are_liability": True,
        },
        "stock_gaps": gaps,
        "missing_parts_count": len(gaps),
        "deposits": deposits,
        "channels": get_estimate_channels(db, branch_id=invoice.branch_id),
        "advance_policy": get_advance_policy(db, branch_id=invoice.branch_id),
    }


def revise_estimate(db: Session, invoice: Invoice, user) -> Invoice:
    """Create a new draft estimate linked to the previous; mark prior as revised."""
    if (invoice.type_of or "").lower() not in ("quote", "quotation", "estimate"):
        raise HTTPException(status_code=400, detail="Only estimates can be revised")
    if (getattr(invoice, "approval_state", None) or "") == "revised":
        raise HTTPException(status_code=400, detail="This estimate was already revised")

    clone = Invoice(
        customer_name=invoice.customer_name,
        customer_address=invoice.customer_address,
        customer_phone=invoice.customer_phone,
        customer_reg_no=invoice.customer_reg_no,
        customer_made=invoice.customer_made,
        customer_mileage=invoice.customer_mileage,
        customer_vin=invoice.customer_vin,
        customer_color=invoice.customer_color,
        customer_chasis=invoice.customer_chasis,
        customer_id=invoice.customer_id,
        car_id=invoice.car_id,
        balance=invoice.balance,
        advance=0.0,  # advances stay on deposits, not as revenue
        net_total=invoice.net_total,
        discount=invoice.discount,
        type_of="quote",
        include_tax=invoice.include_tax,
        tax_amount=invoice.tax_amount,
        status="pending",
        created_by_user=getattr(user, "username", None),
        visit_id=invoice.visit_id,
        job_card_id=invoice.job_card_id,
        parent_quote_id=invoice.id,
        is_variation=False,
        approval_state="draft",
        expected_duration_hours=getattr(invoice, "expected_duration_hours", None),
        expected_completion_at=getattr(invoice, "expected_completion_at", None),
        branch_id=invoice.branch_id,
    )
    db.add(clone)
    db.flush()
    for i in invoice.items or []:
        db.add(
            InvoiceItem(
                invoice_id=clone.id,
                product_name=i.product_name,
                part_number=i.part_number,
                quantity=i.quantity,
                price=i.price,
                proposed_price=i.proposed_price,
                inventory_id=i.inventory_id,
                job_card_line_id=i.job_card_line_id,
                approval_status="pending",
                branch_id=clone.branch_id,
            )
        )
    for l in invoice.labours or []:
        db.add(
            InvoiceLabour(
                invoice_id=clone.id,
                description=l.description,
                price=l.price,
                proposed_price=l.proposed_price,
                labour_code_id=l.labour_code_id,
                std_hours=l.std_hours,
                job_card_line_id=l.job_card_line_id,
                approval_status="pending",
                branch_id=clone.branch_id,
            )
        )
    apply_estimate_money_fields(db, clone)
    invoice.approval_state = "revised"
    db.flush()
    audit_write(
        db,
        user=user,
        action="REVISE",
        module="estimates",
        reference_id=clone.id,
        details=f"Revised estimate from #{invoice.id}",
        old_value={"parent_quote_id": invoice.id},
        new_value={"id": clone.id, "approval_state": "draft"},
    )
    return clone


def stamp_quote_from_job_card(db: Session, invoice: Invoice, card: JobCard | None, data: dict) -> None:
    """Duration / completion / approval_state / required advance after JC→quote."""
    invoice.approval_state = str(data.get("approval_state") or "draft").lower()
    if invoice.approval_state not in APPROVAL_STATES:
        invoice.approval_state = "draft"
    # Quotes must not treat Invoice.advance as cash revenue
    invoice.advance = 0.0

    hours = data.get("expected_duration_hours")
    if hours is None and card:
        hours = sum(float(ln.std_hours or 0) for ln in (card.lines or []) if ln.line_type == "labour")
    if hours is not None:
        invoice.expected_duration_hours = float(hours)

    completion = data.get("expected_completion_at")
    if completion:
        text = str(completion).replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                invoice.expected_completion_at = datetime.strptime(text[:19], fmt)
                break
            except ValueError:
                continue
    elif card and getattr(card, "expected_completion_at", None):
        invoice.expected_completion_at = card.expected_completion_at

    custom = data.get("custom_advance")
    authorized = bool(data.get("authorized_custom_advance") or data.get("reason"))
    if custom is not None and data.get("reason"):
        require_audit_reason(kind="price_edit", reason=data.get("reason"))
        authorized = True
    apply_estimate_money_fields(
        db,
        invoice,
        custom_advance=float(custom) if custom is not None else None,
        authorized_custom=authorized,
    )
