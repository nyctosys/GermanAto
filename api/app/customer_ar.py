"""Customer AR ledger for finalized invoices.

Accrual: debit AR once when an invoice is finalized/locked (revenue recognized).
Cash: credit AR only when verified payments / applied deposits / credit notes post.
Later payments never change net_total or re-post accrual.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.invoice_math import (
    calculate_invoice_status,
    calculate_totals,
    invoice_amount_due,
    invoice_amount_remaining,
)
from app.models import CustomerCreditNote, CustomerLedger, Invoice


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _last_balance(db: Session, customer_id: int) -> Decimal:
    last = (
        db.query(CustomerLedger)
        .filter(CustomerLedger.customer_id == customer_id)
        .order_by(CustomerLedger.date.desc(), CustomerLedger.id.desc())
        .first()
    )
    return _money(last.balance) if last else Decimal("0.00")


def _add_entry(
    db: Session,
    *,
    customer_id: int,
    description: str,
    debit: Decimal | float = 0,
    credit: Decimal | float = 0,
    folio: str | None = None,
    invoice_id: int | None = None,
    credit_note_id: int | None = None,
    cash_received_id: int | None = None,
    username: str | None = None,
    notes: str | None = None,
) -> CustomerLedger:
    d = _money(debit)
    c = _money(credit)
    bal = _last_balance(db, customer_id) + d - c
    entry = CustomerLedger(
        customer_id=customer_id,
        date=date.today(),
        description=description,
        folio=folio,
        debit=d,
        credit=c,
        balance=bal,
        invoice_id=invoice_id,
        credit_note_id=credit_note_id,
        cash_received_id=cash_received_id,
        created_by_user=username,
        payment_notes=notes,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    return entry


def assert_no_duplicate_invoice_for_ro(
    db: Session,
    *,
    repair_order_id: int | None,
    exclude_invoice_id: int | None = None,
) -> None:
    """One finalized/billable invoice per repair order (quotes excluded)."""
    if not repair_order_id:
        return
    q = db.query(Invoice).filter(
        Invoice.repair_order_id == int(repair_order_id),
        Invoice.type_of.ilike("invoice"),
        Invoice.deleted_at.is_(None),
    )
    if exclude_invoice_id:
        q = q.filter(Invoice.id != int(exclude_invoice_id))
    existing = q.first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": f"Repair order #{repair_order_id} already has invoice "
                f"{existing.document_no or existing.id}",
                "invoice_id": existing.id,
            },
        )


def rebuild_invoice_totals(invoice: Invoice) -> None:
    """Recalculate net_total / balance / status from current line rows."""
    items = [
        {"price": float(i.price or 0), "quantity": int(i.quantity or 0)}
        for i in (invoice.items or [])
        if (i.approval_status or "pending").lower() != "rejected"
    ]
    labours = [
        {"price": float(l.price or 0)}
        for l in (invoice.labours or [])
        if (l.approval_status or "pending").lower() != "rejected"
    ]
    # Zeroed rejected lines still on the relation — prefer explicit zeros already applied
    if not items and not labours:
        items = [
            {"price": float(i.price or 0), "quantity": int(i.quantity or 0)}
            for i in (invoice.items or [])
        ]
        labours = [{"price": float(l.price or 0)} for l in (invoice.labours or [])]

    net = calculate_totals(items, labours)
    invoice.net_total = float(net)
    invoice.balance = float(invoice_amount_remaining(invoice))
    invoice.status = calculate_invoice_status(invoice)


def accrual_already_posted(db: Session, invoice_id: int) -> bool:
    return (
        db.query(CustomerLedger)
        .filter(
            CustomerLedger.invoice_id == invoice_id,
            CustomerLedger.debit > 0,
            CustomerLedger.credit == 0,
        )
        .first()
        is not None
    )


def post_accrual_on_finalize(
    db: Session,
    invoice: Invoice,
    *,
    username: str | None = None,
) -> CustomerLedger | None:
    """Recognize revenue once when invoice is issued/locked. Idempotent."""
    if (invoice.type_of or "").lower() != "invoice":
        return None
    if not invoice.customer_id:
        return None
    if accrual_already_posted(db, invoice.id):
        return None
    amount = _money(invoice_amount_due(invoice))
    if amount <= 0:
        return None
    return _add_entry(
        db,
        customer_id=int(invoice.customer_id),
        description=f"Invoice {invoice.document_no or invoice.id} finalized (accrual)",
        debit=amount,
        folio=invoice.document_no or f"INV-{invoice.id}",
        invoice_id=invoice.id,
        username=username,
        notes="Accrual revenue — recognized on finalize, not on payment",
    )


def post_payment_credit(
    db: Session,
    invoice: Invoice,
    *,
    amount: float,
    username: str | None = None,
    cash_received_id: int | None = None,
    notes: str | None = None,
) -> CustomerLedger | None:
    """Cash / verified receipt against AR. Does not change net_total."""
    if not invoice.customer_id:
        return None
    amt = _money(amount)
    if amt <= 0:
        return None
    return _add_entry(
        db,
        customer_id=int(invoice.customer_id),
        description=f"Payment on {invoice.document_no or invoice.id}",
        credit=amt,
        folio=invoice.document_no or f"INV-{invoice.id}",
        invoice_id=invoice.id,
        cash_received_id=cash_received_id,
        username=username,
        notes=notes or "Verified cash receipt",
    )


def post_deposit_application(
    db: Session,
    invoice: Invoice,
    *,
    amount: float,
    username: str | None = None,
) -> CustomerLedger | None:
    """Apply prior advance (liability) to invoice — AR credit, not new cash revenue."""
    if not invoice.customer_id:
        return None
    amt = _money(amount)
    if amt <= 0:
        return None
    return _add_entry(
        db,
        customer_id=int(invoice.customer_id),
        description=f"Deposit applied to {invoice.document_no or invoice.id}",
        credit=amt,
        folio=invoice.document_no or f"INV-{invoice.id}",
        invoice_id=invoice.id,
        username=username,
        notes="Advance applied — not new cash (already received as deposit)",
    )


def create_credit_note(
    db: Session,
    invoice: Invoice,
    *,
    amount: float,
    reason: str,
    username: str | None = None,
) -> tuple[CustomerCreditNote, CustomerLedger | None]:
    """Authorized reduction of billed amount on a posted invoice."""
    if (invoice.type_of or "").lower() != "invoice":
        raise HTTPException(status_code=400, detail="Credit notes apply only to invoices")
    if not (reason or "").strip():
        raise HTTPException(status_code=400, detail="reason is required for credit notes")
    amt = float(_money(amount))
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Credit note amount must be positive")
    due = float(invoice_amount_due(invoice))
    if amt > due + 0.009:
        raise HTTPException(
            status_code=400,
            detail=f"Credit {amt:.2f} exceeds invoice due {due:.2f}",
        )

    note = CustomerCreditNote(
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        amount=amt,
        reason=reason.strip(),
        status="posted",
        created_by_user=username,
        created_at=datetime.utcnow(),
    )
    db.add(note)
    db.flush()

    # Reduce billed total via discount bucket so amount_due drops without rewriting lines
    invoice.discount = float(invoice.discount or 0) + amt
    invoice.balance = float(invoice_amount_remaining(invoice))
    invoice.status = calculate_invoice_status(invoice)

    entry = None
    if invoice.customer_id:
        entry = _add_entry(
            db,
            customer_id=int(invoice.customer_id),
            description=f"Credit note on {invoice.document_no or invoice.id}: {reason.strip()}",
            credit=_money(amt),
            folio=invoice.document_no or f"INV-{invoice.id}",
            invoice_id=invoice.id,
            credit_note_id=note.id,
            username=username,
            notes=reason.strip(),
        )
    return note, entry


def invoice_money_snapshot(invoice: Invoice) -> dict:
    due = float(invoice_amount_due(invoice))
    paid = float((invoice.advance or 0) + (invoice.paid_amount or 0))
    remaining = float(invoice_amount_remaining(invoice))
    return {
        "document_no": invoice.document_no,
        "amount_due": round(due, 2),
        "amount_paid": round(paid, 2),
        "amount_unpaid": round(remaining, 2),
        "net_total": float(invoice.net_total or 0),
        "tax_amount": float(invoice.tax_amount or 0),
        "discount": float(invoice.discount or 0),
        "advance": float(invoice.advance or 0),
        "paid_amount": float(invoice.paid_amount or 0),
        "balance": float(invoice.balance or 0),
        "status": invoice.status,
        "locked": invoice.locked_at is not None,
        "locked_at": invoice.locked_at.strftime("%Y-%m-%d %H:%M:%S") if invoice.locked_at else None,
        "repair_order_id": invoice.repair_order_id,
        "job_card_id": invoice.job_card_id,
        "customer_id": invoice.customer_id,
        "car_id": invoice.car_id,
    }
