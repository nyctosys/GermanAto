"""Month and year closing (spec R15): a checklist, a close that locks the books for the period,
and the closing pack with its proofs."""

import calendar
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import attendance, journal, reports
from app.auth import Actor, require
from app.db import get_db, utcnow
from app.models import CashClose, Invoice, JournalEntry, PayrollRun, PeriodClose, User
from app.routers import moneybook
from app.routers.payroll import run_out
from app.validators import Text

router = APIRouter(prefix="/api", tags=["periods"])
can_close = require("period-close")
can_reopen = require("period-approve")
can_see = require("reports-finance")
KINDS = ("cash", "bank", "wallet")


def label(period: str) -> str:
    return date.fromisoformat(f"{period}-01").strftime("%B %Y") if len(period) == 7 else period


def bounds(period: str) -> tuple[date, date, str]:
    try:
        if len(period) == 4:
            y = int(period)
            return date(y, 1, 1), date(y, 12, 31), "year"
        return (*attendance.month_range(period), "month")
    except ValueError:
        raise HTTPException(422, "Use a month like 2026-10 or a year like 2026")


def _row(db: Session, actor: Actor, kind: str, period: str) -> PeriodClose | None:
    return db.scalar(select(PeriodClose).where(PeriodClose.branch_id == actor.branch.id, PeriodClose.kind == kind, PeriodClose.period == period))


def _is_closed(db: Session, actor: Actor, kind: str, period: str) -> bool:
    r = _row(db, actor, kind, period)
    return bool(r and r.status == "closed")


def months_between(a: date, b: date) -> list[str]:
    out, y, m = [], a.year, a.month
    while (y, m) <= (b.year, b.month):
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def active_months(db: Session, actor: Actor) -> set[str]:
    """Months that have anything posted in them. An empty month has nothing to close."""
    return {m for (m,) in db.execute(select(func.to_char(JournalEntry.entry_date, "YYYY-MM")).where(JournalEntry.branch_id == actor.branch.id).distinct())}


def checklist(db: Session, actor: Actor, month: str) -> dict:
    """Everything that must be true before a month is closed. Blockers stop the close; warnings are shown."""
    start, end, _ = bounds(month)
    items = []

    def item(key, text, ok, detail="", blocking=True, link=None):
        items.append({"key": key, "label": text, "ok": ok, "detail": detail, "blocking": blocking, "link": link})

    item("ended", "The month has ended", end < date.today(), "" if end < date.today() else f"It ends on {end:%d %b %Y}.")

    open_earlier = sorted(m for m in active_months(db, actor) if m < month and not _is_closed(db, actor, "month", m))
    item("earlier", "Earlier months are closed", not open_earlier, f"{label(open_earlier[0])} is still open." if open_earlier else "", link="/periods")

    missing = []
    for direction in ("in", "out"):
        for r in moneybook._gather(db, actor, direction):  # type: ignore[arg-type]
            if r["missing_proof"] and r["status"] == "posted" and not r["signoff"] and start <= r["date"] <= end and (r["source_type"], r["id"]) not in {(m["source_type"], m["id"]) for m in missing}:
                missing.append(r)
    item("proof", "Every payment has proof, or has been accepted by an admin", not missing,
         f"{len(missing)} still waiting." if missing else "", link="/missing-evidence")

    tb = journal.balances(db, actor.branch, as_of=end)
    balanced = sum((d for d, _ in tb.values()), Decimal(0)) == sum((c for _, c in tb.values()), Decimal(0))
    item("balanced", "The books balance", balanced, "" if balanced else "Debits and credits differ. This should never happen; call for help.")

    moved = journal.balances(db, actor.branch, since=start, as_of=end)
    for kind in KINDS:
        code = journal.MONEY_CODE[kind]
        active = any(moved.get(code, (0, 0))) or any(tb.get(code, (0, 0))[0] - tb.get(code, (0, 0))[1] for _ in [0])
        signed = db.scalar(select(func.max(CashClose.close_date)).where(CashClose.branch_id == actor.branch.id, CashClose.account == kind))
        item(f"cash_{kind}", f"The {kind} account was counted and signed on the last day", (not active) or bool(signed and signed >= end),
             f"Last signed count: {signed:%d %b %Y}." if signed and signed < end and active else "" if not active or (signed and signed >= end) else "Never counted.", link="/cash-close")

    payroll = db.scalar(select(PayrollRun).where(PayrollRun.branch_id == actor.branch.id, PayrollRun.month == month, PayrollRun.status != "void"))
    item("payroll_draft", "Payroll for the month is not left as a draft", not (payroll and payroll.status == "draft"), "Approve or throw away the draft." if payroll and payroll.status == "draft" else "", link="/payroll")
    from app.models import Employee
    has_staff = db.scalar(select(func.count()).select_from(Employee).where(Employee.branch_id == actor.branch.id, Employee.joined_on <= end)) > 0
    item("payroll_done", "Payroll was run for the month", bool(payroll) or not has_staff, "No payroll run for this month." if has_staff and not payroll else "", blocking=False, link="/payroll")

    drafts = db.scalar(select(func.count()).select_from(Invoice).where(Invoice.branch_id == actor.branch.id, Invoice.status == "draft",
                                                                         Invoice.created_at < datetime.combine(end, datetime.max.time()).astimezone()))
    item("drafts", "No draft invoices left over", drafts == 0, f"{drafts} draft invoice{'s' if drafts != 1 else ''}." if drafts else "", blocking=False, link="/invoices?status=draft")

    blockers = [i for i in items if i["blocking"] and not i["ok"]]
    return {"period": month, "label": label(month), "items": items, "can_close": not blockers, "blockers": len(blockers),
            "warnings": len([i for i in items if not i["blocking"] and not i["ok"]])}


def status_out(db: Session, actor: Actor, kind: str, period: str) -> dict:
    r = _row(db, actor, kind, period)
    names = {u.id: u.full_name for u in db.scalars(select(User))}
    return {"kind": kind, "period": period, "label": label(period), "status": r.status if r else "open", "closed_at": r.closed_at if r else None,
            "closed_by": names.get(r.created_by) if r and r.status == "closed" else None, "notes": r.notes if r else "",
            "reopened_by": names.get(r.reopened_by) if r else None, "reopen_reason": r.reopen_reason if r else "",
            "reopened_at": r.reopened_at if r else None}


@router.get("/periods")
def periods(actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    """Every month from the first entry in the books to now, and each year, with whether it is closed."""
    first = db.scalar(select(func.min(JournalEntry.entry_date)).where(JournalEntry.branch_id == actor.branch.id)) or date.today()
    months = months_between(first, date.today())
    years = sorted({m[:4] for m in months})
    return {"months": [status_out(db, actor, "month", m) for m in reversed(months)], "years": [status_out(db, actor, "year", y) for y in reversed(years)]}


@router.get("/periods/{period}/checklist")
def get_checklist(period: str, actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    if bounds(period)[2] != "month":
        raise HTTPException(422, "The checklist is for a month")
    return {**checklist(db, actor, period), **status_out(db, actor, "month", period)}


class CloseIn(BaseModel):
    notes: Text = Field(default="", max_length=1000)


@router.post("/periods/{period}/close")
def close_period(period: str, body: CloseIn, actor: Actor = Depends(can_close), db: Session = Depends(get_db)):
    """Locks a finished month: nothing can be posted dated inside it afterwards."""
    start, end, kind = bounds(period)
    if kind == "month":
        c = checklist(db, actor, period)
        if not c["can_close"]:
            raise HTTPException(409, "The checklist isn't complete: " + "; ".join(f"{i['label']}" for i in c["items"] if i["blocking"] and not i["ok"]))
    else:
        if end >= date.today():
            raise HTTPException(422, "A year can be closed after it has ended")
        pending = sorted(m for m in active_months(db, actor) if m.startswith(period) and not _is_closed(db, actor, "month", m))
        if pending:
            raise HTTPException(409, f"Close every month first. {label(pending[0])} is still open.")
    r = _row(db, actor, kind, period)
    if r and r.status == "closed":
        raise HTTPException(409, "Already closed")
    if r:
        r.status, r.closed_at, r.notes = "closed", utcnow(), body.notes
    else:
        db.add(PeriodClose(kind=kind, period=period, status="closed", closed_at=utcnow(), notes=body.notes))
    db.commit()
    return status_out(db, actor, kind, period)


class ReopenIn(BaseModel):
    reason: Text = Field(min_length=5, max_length=500)


@router.post("/periods/{period}/reopen")
def reopen_period(period: str, body: ReopenIn, actor: Actor = Depends(can_reopen), db: Session = Depends(get_db)):
    """An admin unlocks a month, with a reason that is kept. Latest first: a month under a closed year, or before a closed month, stays locked."""
    start, end, kind = bounds(period)
    r = _row(db, actor, kind, period)
    if not r or r.status != "closed":
        raise HTTPException(409, "That period isn't closed")
    if kind == "month":
        if _is_closed(db, actor, "year", period[:4]):
            raise HTTPException(409, f"{period[:4]} is closed. Reopen the year first.")
        later = [m for m in months_between(date.fromisoformat(f"{period}-01"), date.today())[1:] if _is_closed(db, actor, "month", m)]
        if later:
            raise HTTPException(409, f"{label(later[0])} is closed after it. Reopen the latest month first.")
    r.status, r.reopen_reason, r.reopened_at, r.reopened_by = "open", body.reason, utcnow(), actor.user.id
    db.commit()
    return status_out(db, actor, kind, period)


@router.get("/periods/{period}/pack")
def pack(period: str, actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    """Everything a closed month is judged by, in one place: profit and loss, cash, what is owed to us and by us, stock, proofs."""
    start, end, kind = bounds(period)
    branch = actor.branch
    entries = []
    for direction in ("in", "out"):
        for r in moneybook._gather(db, actor, direction):  # type: ignore[arg-type]
            if start <= r["date"] <= end and r["status"] == "posted" and (r["source_type"], r["id"], direction if r["source"] != "transfer" else "x") not in {(e["source_type"], e["id"], e["direction"] if e["source"] != "transfer" else "x") for e in entries}:
                entries.append({**{k: r[k] for k in ("number", "date", "source", "source_type", "id", "party", "account", "amount", "proof_url", "no_proof_reason", "signoff")}, "direction": direction})
    entries.sort(key=lambda e: (e["date"], e["number"]))
    closes = [{"account": c.account, "close_date": c.close_date, "expected": c.expected, "counted": c.counted, "difference": c.difference, "reason": c.reason}
              for c in db.scalars(select(CashClose).where(CashClose.branch_id == branch.id, CashClose.close_date >= start, CashClose.close_date <= end).order_by(CashClose.close_date))]
    runs = [run_out(db, r) for r in db.scalars(select(PayrollRun).where(PayrollRun.branch_id == branch.id, PayrollRun.status != "void",
                                                                    PayrollRun.month >= start.strftime("%Y-%m"), PayrollRun.month <= end.strftime("%Y-%m")))]
    months = [{"month": m, **{k: v for k, v in reports.pnl(db, branch, *attendance.month_range(m)).items() if k in ("revenue", "net_profit", "total_expenses")}}
              for m in months_between(start, end)] if kind == "year" else []
    return {"period": period, "label": label(period), "kind": kind, "status": status_out(db, actor, kind, period),
            "pnl": reports.pnl(db, branch, start, end), "cashflow": reports.cashflow(db, branch, start, end), "months": months,
            "receivables": reports.receivables(db, branch, min(end, date.today())), "payables": reports.payables(db, branch, min(end, date.today())),
            "stock": {"total": reports.stock_value(db, branch)["total"]}, "cash_closes": closes, "entries": entries,
            "payroll": [{"month": r["month"], "status": r["status"], "gross": r["totals"]["gross"], "net": r["totals"]["net"]} for r in runs],
            "journal_balance": journal.balances(db, branch, as_of=end)}
