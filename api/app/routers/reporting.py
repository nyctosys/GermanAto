"""The report endpoints and the dashboard. Each is a thin wrapper over app/reports.py."""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import attendance, journal, reports
from app.auth import Actor, current_actor, require
from app.db import get_db
from app.models import Item, MoneyEntry, Quotation, RepairOrder, Visit
from app.routers import moneybook
from app.pricing import totals

router = APIRouter(prefix="/api", tags=["reports"])
finance = require("reports-finance")
ops = require("reports-ops")


def span(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = date.today()
    start, end = date_from or today.replace(day=1), date_to or today
    if end < start:
        raise HTTPException(422, "The end date is before the start date")
    return start, end


@router.get("/reports/pnl")
def r_pnl(date_from: date | None = None, date_to: date | None = None, actor: Actor = Depends(finance), db: Session = Depends(get_db)):
    return reports.pnl(db, actor.branch, *span(date_from, date_to))


@router.get("/reports/cashflow")
def r_cashflow(date_from: date | None = None, date_to: date | None = None, actor: Actor = Depends(finance), db: Session = Depends(get_db)):
    return reports.cashflow(db, actor.branch, *span(date_from, date_to))


@router.get("/reports/receivables")
def r_receivables(actor: Actor = Depends(finance), db: Session = Depends(get_db)):
    return reports.receivables(db, actor.branch)


@router.get("/reports/payables")
def r_payables(actor: Actor = Depends(finance), db: Session = Depends(get_db)):
    return reports.payables(db, actor.branch)


@router.get("/reports/stock-value")
def r_stock(actor: Actor = Depends(finance), db: Session = Depends(get_db)):
    return reports.stock_value(db, actor.branch)


@router.get("/reports/discounts")
def r_discounts(date_from: date | None = None, date_to: date | None = None, actor: Actor = Depends(finance), db: Session = Depends(get_db)):
    return reports.discounts_and_voids(db, actor.branch, *span(date_from, date_to))


@router.get("/reports/operations")
def r_ops(date_from: date | None = None, date_to: date | None = None, actor: Actor = Depends(ops), db: Session = Depends(get_db)):
    return reports.operations(db, actor.branch, *span(date_from, date_to))


@router.get("/reports/hr")
def r_hr(month: str | None = None, actor: Actor = Depends(require("hr")), db: Session = Depends(get_db)):
    month = month or date.today().strftime("%Y-%m")
    try:
        attendance.month_range(month)
    except ValueError:
        raise HTTPException(422, "Use a month like 2026-10")
    return reports.hr_report(db, actor.branch, month)


@router.get("/dashboard")
def dashboard(actor: Actor = Depends(require("dashboard")), db: Session = Depends(get_db)):
    """What the owner looks at first. Workshop and stock figures for everyone with the dashboard; money for those who may see finance."""
    branch, today = actor.branch, date.today()
    month_start = today.replace(day=1)
    in_workshop = db.scalar(select(func.count()).select_from(Visit).where(Visit.branch_id == branch.id, Visit.status == "open"))
    quotes = db.scalars(select(Quotation).where(Quotation.branch_id == branch.id, Quotation.status.in_(("draft", "sent")))).all()
    ros = db.scalars(select(RepairOrder).where(RepairOrder.branch_id == branch.id, RepairOrder.status.not_in(("delivered",)))).all()
    out = {"workshop": {"cars_in": in_workshop, "open_quotes": len(quotes), "quotes_waiting": sum(1 for q in quotes if q.status == "sent"),
                        "repair_orders": len(ros), "ready_for_pickup": sum(1 for r in ros if r.status == "ready"), "on_hold": sum(1 for r in ros if r.status == "on_hold")}}
    stock = reports.stock_value(db, branch)
    out["stock"] = {"low_stock": stock["low_stock"], "items": len(stock["items"])}
    if actor.can("reports-finance"):
        cash = {k: journal.money_balance(db, branch, k) for k in journal.MONEY_CODE}
        pnl = reports.pnl(db, branch, month_start, today)
        rec, pay = reports.receivables(db, branch), reports.payables(db, branch)
        mi = moneybook.page(db, actor, "in", date_from=month_start, date_to=today, source=None, account=None, q="", missing_proof=False, limit=1)
        mo = moneybook.page(db, actor, "out", date_from=month_start, date_to=today, source=None, account=None, q="", missing_proof=False, limit=1)
        from app.routers.periods import checklist, months_between
        first = db.scalar(select(func.min(journal.JournalEntry.entry_date)).where(journal.JournalEntry.branch_id == branch.id))
        unclosed = [m for m in months_between(first, today)[:-1] if m not in {p for (p,) in db.execute(select(journal.PeriodClose.period).where(journal.PeriodClose.branch_id == branch.id, journal.PeriodClose.kind == "month", journal.PeriodClose.status == "closed"))}] if first else []
        out["money"] = {"cash": cash, "cash_total": sum(cash.values(), Decimal(0)), "money_in_month": mi["total"], "money_out_month": mo["total"],
                        "revenue_month": pnl["revenue"]["total"], "profit_month": pnl["net_profit"], "receivables": rec["total"],
                        "overdue_receivables": sum((r["balance"] for r in rec["rows"] if r["bucket"] in ("31-60", "61-90", "90+")), Decimal(0)),
                        "payables": pay["total"], "overdue_payables": sum((r["balance"] for r in pay["rows"] if r["days_overdue"] > 0), Decimal(0)),
                        "stock_value": stock["total"]}
        out["alerts"] = {"missing_proof": mi["missing_proof"] + mo["missing_proof"], "unclosed_months": unclosed, "low_stock": stock["low_stock"],
                         "overdue_bills": sum(1 for r in pay["rows"] if r["days_overdue"] > 0), "overdue_invoices": sum(1 for r in rec["rows"] if r["bucket"] in ("31-60", "61-90", "90+"))}
    return out
