"""Money In / Money Out facade aggregates (no double-counting)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.models import CashReceived, CustomerDeposit, Expense, Invoice, VendorLedger

router = APIRouter(tags=["money"])


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


def _range(days: int) -> tuple[datetime, datetime]:
    end = datetime.utcnow()
    start = end - timedelta(days=max(1, days))
    return start, end


@router.get("/money-in")
def money_in(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "accountant", "manager"])),
    days: int = Query(30, ge=1, le=365),
):
    """Inflows: cash received + invoice payments (paid_amount deltas via history not re-summed) + open deposits.

    Deposits are liabilities until applied — listed separately, not added to revenue total.
    Invoice payments use Invoice.paid_amount for the period (created/updated recently).
    """
    start, end = _range(days)
    start_d = start.date()

    cash_rows = (
        db.query(CashReceived)
        .filter(CashReceived.deleted_at.is_(None), CashReceived.date >= start_d)
        .order_by(CashReceived.date.desc())
        .limit(200)
        .all()
    )
    cash_total = sum(float(r.amount or 0) for r in cash_rows)

    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.deleted_at.is_(None),
            Invoice.type_of == "invoice",
            Invoice.updated_at >= start,
        )
        .limit(500)
        .all()
    )
    # paid_amount is cumulative; for facade we show period cash + deposits applied only
    # to avoid double-counting cash_received that also updated invoices.
    payment_total = sum(float(inv.paid_amount or 0) for inv in invoices if (inv.paid_amount or 0) > 0)

    deposits_open = (
        db.query(CustomerDeposit)
        .filter(CustomerDeposit.deleted_at.is_(None), CustomerDeposit.status == "open")
        .all()
    )
    deposits_applied = (
        db.query(CustomerDeposit)
        .filter(
            CustomerDeposit.deleted_at.is_(None),
            CustomerDeposit.status == "applied",
            CustomerDeposit.updated_at >= start,
        )
        .all()
    )
    liability = sum(float(d.amount or 0) for d in deposits_open)
    applied = sum(float(d.amount or 0) for d in deposits_applied)

    # Primary inflow figure: cash received + deposits applied (revenue recognition).
    # Do not add invoice.paid_amount on top of cash_received (overlap risk).
    inflow_total = round(cash_total + applied, 2)

    return _json(
        {
            "period_days": days,
            "inflow_total": inflow_total,
            "cash_received_total": round(cash_total, 2),
            "deposits_applied_total": round(applied, 2),
            "deposits_liability_open": round(liability, 2),
            "invoice_paid_amount_snapshot": round(payment_total, 2),
            "note": "inflow_total = cash_received + deposits applied (liabilities not counted as revenue)",
            "cash_received": [
                {
                    "id": r.id,
                    "date": r.date.isoformat() if r.date else None,
                    "amount": r.amount,
                    "description": getattr(r, "description", None) or getattr(r, "notes", None),
                }
                for r in cash_rows[:50]
            ],
            "deposits_open": [d.to_dict() for d in deposits_open[:50]],
            "deposits_applied": [d.to_dict() for d in deposits_applied[:50]],
        }
    )


@router.get("/money-out")
def money_out(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "accountant", "manager"])),
    days: int = Query(30, ge=1, le=365),
):
    start, end = _range(days)
    start_d = start.date()

    expenses = (
        db.query(Expense)
        .filter(Expense.deleted_at.is_(None), Expense.date >= start_d)
        .order_by(Expense.date.desc())
        .limit(200)
        .all()
    )
    expense_total = sum(float(e.amount or 0) for e in expenses)

    # Vendor payments = ledger credits (money out to suppliers)
    credits = (
        db.query(VendorLedger)
        .filter(VendorLedger.deleted_at.is_(None), VendorLedger.date >= start_d, VendorLedger.credit > 0)
        .order_by(VendorLedger.date.desc())
        .limit(200)
        .all()
    )
    vendor_paid = sum(float(c.credit or 0) for c in credits)

    outflow = round(expense_total + vendor_paid, 2)
    return _json(
        {
            "period_days": days,
            "outflow_total": outflow,
            "expenses_total": round(expense_total, 2),
            "vendor_payments_total": round(vendor_paid, 2),
            "note": "Payroll runs listed separately in HR; not double-counted here",
            "expenses": [
                {
                    "id": e.id,
                    "date": e.date.isoformat() if e.date else None,
                    "category": e.category,
                    "description": e.description,
                    "amount": e.amount,
                }
                for e in expenses[:50]
            ],
            "vendor_payments": [c.to_dict() for c in credits[:50]],
        }
    )
