"""Strict workshop pipeline guards: visit → job card → quote → RO → QC → invoice → gate pass."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.foundation.overrides import assert_payment_gate_override
from app.foundation.settings import payment_gate_enabled
from app.invoice_math import invoice_amount_remaining
from app.models import GatePass, Invoice, JobCard, QcSignoff, RepairOrder, Variation


def assert_invoice_unlocked(invoice: Invoice) -> None:
    if invoice.locked_at is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Invoice is locked after issue. Use a credit note / reversal.",
                "locked": True,
            },
        )


def lock_invoice(invoice: Invoice) -> None:
    if invoice.locked_at is None:
        invoice.locked_at = datetime.utcnow()


def assert_can_create_job_card(db: Session, *, car_id: int | None, visit_id: int | None) -> None:
    from app.visits import require_visit_for_job_card

    require_visit_for_job_card(db, car_id=car_id, visit_id=visit_id, for_repair_order=False)


def assert_quote_from_job_card(job_card: JobCard | None) -> JobCard:
    if job_card is None:
        raise HTTPException(status_code=400, detail="Job card is required to build a quotation")
    if job_card.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot quote a cancelled job card")
    if job_card.status == "draft":
        raise HTTPException(
            status_code=400,
            detail="Open the draft job card before building a quotation",
        )
    return job_card


def assert_can_open_ro_from_quote(db: Session, quote: Invoice) -> None:
    if (quote.type_of or "").lower() != "quote":
        raise HTTPException(status_code=400, detail="Repair order must open from an approved quote")
    items = list(quote.items or [])
    labours = list(quote.labours or [])
    if not items and not labours:
        raise HTTPException(status_code=400, detail="Quote has no lines")
    statuses = [(i.approval_status or "pending").lower() for i in items] + [
        (l.approval_status or "pending").lower() for l in labours
    ]
    approved = [s for s in statuses if s == "approved"]
    # Legacy quotes: every line still "pending" (pre-approval flow) may open an RO.
    legacy_all_pending = statuses and all(s == "pending" for s in statuses)
    if not approved and not legacy_all_pending:
        raise HTTPException(
            status_code=400,
            detail="At least one quote line must be customer-approved before opening an RO",
        )


def assert_qc_before_invoice(db: Session, repair_order_id: int | None) -> QcSignoff:
    if not repair_order_id:
        raise HTTPException(status_code=400, detail="Invoice requires a repair order with QC sign-off")
    qc = (
        db.query(QcSignoff)
        .filter(QcSignoff.repair_order_id == repair_order_id, QcSignoff.deleted_at.is_(None))
        .order_by(QcSignoff.id.desc())
        .first()
    )
    if qc is None:
        raise HTTPException(status_code=400, detail="QC sign-off required before issuing an invoice")
    return qc


def assert_variation_line_billable(db: Session, *, variation_id: int | None, approval_status: str) -> None:
    if variation_id is None:
        return
    if (approval_status or "").lower() != "approved":
        raise HTTPException(
            status_code=400,
            detail="Unapproved variation extras cannot be worked or billed",
        )
    var = db.get(Variation, variation_id)
    if var and var.status == "rejected":
        raise HTTPException(status_code=400, detail="Variation was rejected")


def assert_payment_gate_for_delivery(
    db: Session,
    user,
    invoice: Invoice | None,
    *,
    bypass: bool = False,
    reason: str | None = None,
    branch_id: str | None = None,
) -> str | None:
    """Block delivery / gate pass when balance > 0 unless override."""
    if invoice is None:
        return None
    if (invoice.type_of or "").lower() != "invoice":
        return None
    remaining = invoice_amount_remaining(invoice)
    if remaining <= 0:
        return None
    if not payment_gate_enabled(db, branch_id=branch_id):
        return None
    if not bypass:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Payment gate: balance {remaining:.2f} PKR still owed. Override required to deliver.",
                "balance": remaining,
                "require_override": "override_payment_gate",
            },
        )
    return assert_payment_gate_override(db, user, bypass=True, reason=reason, branch_id=branch_id)


def assert_no_duplicate_gate_pass(db: Session, repair_order_id: int) -> None:
    existing = (
        db.query(GatePass)
        .filter(GatePass.repair_order_id == repair_order_id, GatePass.deleted_at.is_(None))
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Gate pass already exists for this repair order")


def discount_pct(discount: float, net_total: float) -> float:
    if not net_total or net_total <= 0:
        return 100.0 if discount and discount > 0 else 0.0
    return (float(discount) / float(net_total)) * 100.0


def mark_ro_delivered(ro: RepairOrder) -> None:
    ro.current_status = "delivered"


def next_action(db: Session, *, job_card_id: int | None = None, repair_order_id: int | None = None) -> dict:
    """Return human-readable next step + deep-link hints for workshop staff."""
    from app.models import GatePass, Invoice, JobCard, QcSignoff
    from app.invoice_math import invoice_amount_remaining

    if job_card_id:
        card = db.get(JobCard, job_card_id)
        if not card:
            return {"label": "Job card not found", "code": "missing"}
        if not card.quote_invoice_id:
            return {
                "label": "Build quotation from this job card",
                "code": "build_quote",
                "href": f"/job-cards/{card.id}",
            }
        quote = db.get(Invoice, card.quote_invoice_id)
        if quote:
            pending = any(
                (i.approval_status or "pending") == "pending" for i in (quote.items or [])
            ) or any((l.approval_status or "pending") == "pending" for l in (quote.labours or []))
            if pending:
                return {
                    "label": "Send quote for customer line approval",
                    "code": "await_approval",
                    "href": "/quotes/pending",
                    "invoice_id": quote.id,
                }
            return {
                "label": "Open repair order from approved quote",
                "code": "open_ro",
                "href": "/quotes/pending",
                "invoice_id": quote.id,
            }
        return {"label": "Continue on quote", "code": "quote", "href": "/quotes/pending"}

    if repair_order_id:
        ro = db.get(RepairOrder, repair_order_id)
        if not ro:
            return {"label": "Repair order not found", "code": "missing"}
        gp = (
            db.query(GatePass)
            .filter(GatePass.repair_order_id == ro.id, GatePass.deleted_at.is_(None))
            .first()
        )
        if gp:
            return {"label": "Closed — vehicle released", "code": "closed", "href": f"/repair-orders/{ro.id}/pipeline"}

        qc = (
            db.query(QcSignoff)
            .filter(QcSignoff.repair_order_id == ro.id, QcSignoff.deleted_at.is_(None))
            .first()
        )
        if not qc:
            return {
                "label": "Complete QC sign-off before invoicing",
                "code": "qc",
                "href": f"/repair-orders/{ro.id}/pipeline",
            }

        inv = (
            db.query(Invoice)
            .filter(
                Invoice.repair_order_id == ro.id,
                Invoice.type_of == "invoice",
                Invoice.deleted_at.is_(None),
            )
            .order_by(Invoice.id.desc())
            .first()
        )
        if not inv and ro.quote_invoice_id:
            return {
                "label": "Convert approved quote to invoice (after QC)",
                "code": "invoice",
                "href": "/quotes/pending",
                "invoice_id": ro.quote_invoice_id,
            }
        if inv and invoice_amount_remaining(inv) > 0:
            return {
                "label": f"Collect payment — balance {invoice_amount_remaining(inv):.2f} PKR",
                "code": "payment",
                "href": f"/invoices/{inv.id}/edit",
                "invoice_id": inv.id,
            }
        return {
            "label": "Create gate pass / handover",
            "code": "gate_pass",
            "href": f"/repair-orders/{ro.id}/pipeline",
        }

    return {"label": "Select a job card or repair order", "code": "idle"}
