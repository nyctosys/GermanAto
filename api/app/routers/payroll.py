"""Salary advances and monthly payroll. Pay comes from attendance, advances are recovered out
of it, and the money paid out lands on the Money Out page like every other payment."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import attendance, posting
from app.auth import Actor, require
from app.db import get_db, utcnow
from app.models import Employee, MoneyEntry, PayrollLine, PayrollRun, User
from app.numbering import next_number
from app.pricing import money
from app.routers.cashclose import assert_day_open
from app.routers.estimates import Proof
from app.routers.workshop import _attach
from app.validators import Text

router = APIRouter(prefix="/api", tags=["payroll"])
can_pay = require("payroll")


def _employee(db: Session, actor: Actor, employee_id: uuid.UUID) -> Employee:
    e = db.get(Employee, employee_id)
    if not e or e.branch_id != actor.branch.id:
        raise HTTPException(404, "Employee not found")
    return e


def outstanding(db: Session, employee_id: uuid.UUID) -> tuple[Decimal, Decimal]:
    """Advances given and advances already recovered through approved payroll."""
    given = db.scalar(select(func.coalesce(func.sum(MoneyEntry.amount), 0)).where(
        MoneyEntry.employee_id == employee_id, MoneyEntry.kind == "salary_advance", MoneyEntry.status == "posted"))
    recovered = db.scalar(select(func.coalesce(func.sum(PayrollLine.advance_recovery), 0)).join(PayrollRun, PayrollRun.id == PayrollLine.payroll_run_id)
                          .where(PayrollLine.employee_id == employee_id, PayrollRun.status.in_(("approved", "paid"))))
    return given, recovered


# --- salary advances -------------------------------------------------------------------------------------

class AdvanceIn(Proof):
    employee_id: uuid.UUID
    amount: Decimal = Field(gt=0, le=100_000_000, decimal_places=2)
    account: Literal["cash", "bank", "wallet"]
    reference: Text = Field(default="", max_length=60)
    note: Text = Field(default="", max_length=500)


def entry_out(e: MoneyEntry) -> dict:
    return {"id": e.id, "number": e.number, "kind": e.kind, "status": e.status, "occurred_on": e.occurred_on, "account": e.account, "amount": e.amount,
            "reference": e.reference, "note": e.note, "proof_url": f"/api/attachments/{e.proof_id}/file" if e.proof_id else None,
            "no_proof_reason": e.no_proof_reason, "employee_id": e.employee_id}


@router.post("/salary-advances", status_code=201)
def give_advance(body: AdvanceIn, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    """Money lent against salary, paid out now and taken back through payroll. Never more than a month's pay is outstanding."""
    emp = _employee(db, actor, body.employee_id)
    if not emp.is_active:
        raise HTTPException(422, f"{emp.full_name} is no longer active")
    given, recovered = outstanding(db, emp.id)
    if given - recovered + body.amount > emp.monthly_salary:
        raise HTTPException(422, f"That would put {given - recovered + body.amount:,.2f} of advances outstanding, more than a month's pay ({emp.monthly_salary:,.2f})")
    if body.account != "cash" and not body.reference and not body.proof_id:
        raise HTTPException(422, "Add the transaction reference or a screenshot for a bank or wallet payment")
    assert_day_open(db, actor.branch.id, {body.account}, date.today())
    e = MoneyEntry(number=next_number(db, actor.branch, "salary_advance"), kind="salary_advance", occurred_on=date.today(), account=body.account,
                   amount=body.amount, party=emp.full_name, reference=body.reference, note=body.note, proof_id=body.proof_id,
                   no_proof_reason=body.no_proof_reason, employee_id=emp.id)
    db.add(e)
    db.flush()
    if body.proof_id:
        _attach(db, actor, [body.proof_id], "money_entries", e.id)
    posting.money_entry(db, actor.branch, e)
    db.commit()
    return entry_out(e)


@router.get("/salary-advances")
def advances(employee_id: uuid.UUID | None = None, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    emps = db.scalars(select(Employee).where(Employee.branch_id == actor.branch.id, Employee.is_active).order_by(Employee.full_name)).all()
    summary = []
    for e in emps:
        given, recovered = outstanding(db, e.id)
        summary.append({"employee": {"id": e.id, "number": e.number, "full_name": e.full_name, "monthly_salary": e.monthly_salary},
                        "advanced": given, "recovered": recovered, "outstanding": given - recovered})
    stmt = select(MoneyEntry).where(MoneyEntry.branch_id == actor.branch.id, MoneyEntry.kind == "salary_advance").order_by(MoneyEntry.created_at.desc()).limit(100)
    if employee_id:
        stmt = stmt.where(MoneyEntry.employee_id == employee_id)
    names = {e.id: e.full_name for e in emps}
    return {"employees": summary, "entries": [{**entry_out(m), "employee": names.get(m.employee_id, "")} for m in db.scalars(stmt)]}


# --- payroll runs ------------------------------------------------------------------------------------------

def _get_run(db: Session, actor: Actor, run_id: uuid.UUID, *, lock: bool = False) -> PayrollRun:
    stmt = select(PayrollRun).where(PayrollRun.id == run_id)
    run = db.scalar(stmt.with_for_update() if lock else stmt)
    if not run or run.branch_id != actor.branch.id:
        raise HTTPException(404, "Payroll run not found")
    return run


def month_working_days(e: Employee, start: date, end: date) -> int:
    d, n = start, 0
    while d <= end:
        n += d.weekday() != e.weekly_off
        d += timedelta(days=1)
    return n


def figures(db: Session, e: Employee, month: str) -> dict:
    """Pay for the month from attendance: base for the days they were employed, less a day's pay for each unexcused absence or unpaid leave day."""
    start, end = attendance.month_range(month)
    t = attendance.summarise(db, e, start, end, today=end)
    full = month_working_days(e, start, end)
    if t.working_days == 0 or full == 0:
        return {}
    base = money(e.monthly_salary * t.working_days / full)
    deduction = min(money(e.monthly_salary / full * (t.absent + t.unpaid_leave)), base)
    return {"monthly_salary": e.monthly_salary, "working_days": t.working_days, "month_working_days": full, "absent_days": t.absent,
            "unpaid_leave_days": t.unpaid_leave, "late_days": t.late, "base_pay": base, "deduction": deduction}


def _net(l: PayrollLine) -> Decimal:
    return l.base_pay - l.deduction + l.adjustment - l.advance_recovery


def line_out(db: Session, l: PayrollLine, e: Employee | None = None) -> dict:
    e = e or db.get(Employee, l.employee_id)
    paid = db.scalar(select(MoneyEntry).where(MoneyEntry.payroll_line_id == l.id, MoneyEntry.status == "posted"))
    return {"id": l.id, "employee": {"id": e.id, "number": e.number, "full_name": e.full_name, "title": e.title, "cnic": e.cnic},
            **{k: getattr(l, k) for k in ("monthly_salary", "working_days", "month_working_days", "absent_days", "unpaid_leave_days", "late_days",
                                           "base_pay", "deduction", "adjustment", "adjustment_reason", "advance_recovery", "net_pay")},
            "gross_pay": l.base_pay - l.deduction + l.adjustment, "outstanding_advance": outstanding(db, e.id)[0] - outstanding(db, e.id)[1],
            "paid": paid and {"id": paid.id, "number": paid.number, "account": paid.account, "occurred_on": paid.occurred_on,
                              "proof_url": f"/api/attachments/{paid.proof_id}/file" if paid.proof_id else None, "no_proof_reason": paid.no_proof_reason}}


def run_out(db: Session, run: PayrollRun) -> dict:
    lines = [line_out(db, l) for l in run.lines]
    by = db.get(User, run.approved_by) if run.approved_by else None
    lines.sort(key=lambda l: l["employee"]["full_name"])
    return {"id": run.id, "number": run.number, "month": run.month, "status": run.status, "version": run.version, "notes": run.notes,
            "approved_at": run.approved_at, "approved_by": by.full_name if by else None, "lines": lines,
            "totals": {"gross": sum((l["gross_pay"] for l in lines), Decimal(0)), "recovery": sum((l["advance_recovery"] for l in lines), Decimal(0)),
                       "net": sum((l["net_pay"] for l in lines), Decimal(0)),
                       "paid": sum((l["net_pay"] for l in lines if l["paid"]), Decimal(0))}}


class RunIn(BaseModel):
    month: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")


@router.post("/payroll-runs", status_code=201)
def start_run(body: RunIn, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    """Works out everyone's pay for a finished month. Draft until approved, so it can be checked and adjusted."""
    start, end = attendance.month_range(body.month)
    if end >= date.today():
        raise HTTPException(422, "Payroll is run after the month has ended")
    if db.scalar(select(PayrollRun.id).where(PayrollRun.branch_id == actor.branch.id, PayrollRun.month == body.month, PayrollRun.status != "void")):
        raise HTTPException(409, "There is already a payroll run for this month")
    emps = db.scalars(select(Employee).where(Employee.branch_id == actor.branch.id, Employee.joined_on <= end,
                                             or_(Employee.left_on.is_(None), Employee.left_on >= start)).order_by(Employee.full_name)).all()
    run = PayrollRun(number=next_number(db, actor.branch, "payroll_run"), month=body.month)
    for e in emps:
        f = figures(db, e, body.month)
        if not f:
            continue
        given, recovered = outstanding(db, e.id)
        gross = f["base_pay"] - f["deduction"]
        recovery = min(max(given - recovered, Decimal(0)), gross)
        line = PayrollLine(employee_id=e.id, advance_recovery=recovery, net_pay=gross - recovery, **f)
        run.lines.append(line)
    if not run.lines:
        raise HTTPException(422, "Nobody was employed that month")
    db.add(run)
    db.commit()
    return run_out(db, run)


@router.get("/payroll-runs")
def list_runs(actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    runs = db.scalars(select(PayrollRun).where(PayrollRun.branch_id == actor.branch.id, PayrollRun.status != "void").order_by(PayrollRun.month.desc())).all()
    out = []
    for r in runs:
        o = run_out(db, r)
        out.append({k: o[k] for k in ("id", "number", "month", "status", "totals")} | {"people": len(o["lines"])})
    return out


@router.get("/payroll-runs/{run_id}")
def get_run(run_id: uuid.UUID, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    return run_out(db, _get_run(db, actor, run_id))


@router.get("/payroll-runs/{run_id}/lines/{line_id}")
def payslip(run_id: uuid.UUID, line_id: uuid.UUID, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    run = _get_run(db, actor, run_id)
    line = next((l for l in run.lines if l.id == line_id), None)
    if not line:
        raise HTTPException(404, "Line not found")
    return {"run": {"number": run.number, "month": run.month, "status": run.status}, "line": line_out(db, line)}


class LineEdit(BaseModel):
    adjustment: Decimal = Field(default=Decimal(0), ge=-100_000_000, le=100_000_000, decimal_places=2)
    adjustment_reason: Text = Field(default="", max_length=200)
    advance_recovery: Decimal = Field(default=Decimal(0), ge=0, le=100_000_000, decimal_places=2)


@router.put("/payroll-runs/{run_id}/lines/{line_id}")
def edit_line(run_id: uuid.UUID, line_id: uuid.UUID, body: LineEdit, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    run = _get_run(db, actor, run_id, lock=True)
    if run.status != "draft":
        raise HTTPException(409, "An approved payroll run can't be changed")
    line = next((l for l in run.lines if l.id == line_id), None)
    if not line:
        raise HTTPException(404, "Line not found")
    if body.adjustment != 0 and len(body.adjustment_reason) < 3:
        raise HTTPException(422, "Say what the bonus or deduction is for")
    given, recovered = outstanding(db, line.employee_id)
    if body.advance_recovery > max(given - recovered, Decimal(0)):
        raise HTTPException(422, f"Only {max(given - recovered, Decimal(0)):,.2f} of advances is outstanding for this person")
    gross = line.base_pay - line.deduction + body.adjustment
    if body.advance_recovery > gross:
        raise HTTPException(422, "The recovery can't be more than the pay it comes out of")
    line.adjustment, line.adjustment_reason, line.advance_recovery = body.adjustment, body.adjustment_reason if body.adjustment else "", body.advance_recovery
    line.net_pay = gross - body.advance_recovery
    db.commit()
    return run_out(db, run)


@router.post("/payroll-runs/{run_id}/refresh")
def refresh(run_id: uuid.UUID, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    """Re-reads attendance (after a correction) and keeps the adjustments already entered."""
    run = _get_run(db, actor, run_id, lock=True)
    if run.status != "draft":
        raise HTTPException(409, "Only a draft can be refreshed")
    for l in list(run.lines):
        e = db.get(Employee, l.employee_id)
        f = figures(db, e, run.month)
        if not f:
            run.lines.remove(l)
            continue
        for k, v in f.items():
            setattr(l, k, v)
        given, recovered = outstanding(db, e.id)
        gross = l.base_pay - l.deduction + l.adjustment
        l.advance_recovery = min(l.advance_recovery, max(given - recovered, Decimal(0)), max(gross, Decimal(0)))
        l.net_pay = gross - l.advance_recovery
        if l.net_pay < 0:
            raise HTTPException(422, f"{e.full_name}'s adjustment makes the pay negative. Fix it first.")
    db.commit()
    return run_out(db, run)


@router.post("/payroll-runs/{run_id}/approve")
def approve(run_id: uuid.UUID, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    """Fixes the figures and books the month's salary expense. Advances recovered here stop being outstanding."""
    run = _get_run(db, actor, run_id, lock=True)
    if run.status != "draft":
        raise HTTPException(409, "Already approved")
    for l in run.lines:
        if _net(l) != l.net_pay or l.net_pay < 0:
            raise HTTPException(409, "The figures changed. Refresh the run and check them again.")
        given, recovered = outstanding(db, l.employee_id)
        if l.advance_recovery > given - recovered:
            raise HTTPException(409, "An advance was changed since this run was drafted. Refresh it.")
    run.status, run.approved_at, run.approved_by = "approved", utcnow(), actor.user.id
    db.flush()
    posting.payroll_approved(db, actor.branch, run, run.lines)
    db.commit()
    return run_out(db, run)


@router.post("/payroll-runs/{run_id}/void")
def void_run(run_id: uuid.UUID, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    run = _get_run(db, actor, run_id, lock=True)
    if run.status != "draft":
        raise HTTPException(409, "Only a draft can be thrown away")
    run.status = "void"
    db.commit()
    return {"ok": True}


class PayIn(Proof):
    account: Literal["cash", "bank", "wallet"]
    reference: Text = Field(default="", max_length=60)
    note: Text = Field(default="", max_length=500)


@router.post("/payroll-runs/{run_id}/lines/{line_id}/pay", status_code=201)
def pay_line(run_id: uuid.UUID, line_id: uuid.UUID, body: PayIn, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    """Pays one person their net pay. It appears on Money out, with proof or a reason, like every payment."""
    run = _get_run(db, actor, run_id, lock=True)
    if run.status not in ("approved", "paid"):
        raise HTTPException(409, "Approve the payroll run before paying")
    line = next((l for l in run.lines if l.id == line_id), None)
    if not line:
        raise HTTPException(404, "Line not found")
    if line.net_pay <= 0:
        raise HTTPException(409, "There is nothing to pay on this line")
    if db.scalar(select(MoneyEntry.id).where(MoneyEntry.payroll_line_id == line.id, MoneyEntry.status == "posted")):
        raise HTTPException(409, "Already paid")
    if body.account != "cash" and not body.reference and not body.proof_id:
        raise HTTPException(422, "Add the transaction reference or a screenshot for a bank or wallet payment")
    assert_day_open(db, actor.branch.id, {body.account}, date.today())
    emp = db.get(Employee, line.employee_id)
    e = MoneyEntry(number=next_number(db, actor.branch, "salary"), kind="salary", occurred_on=date.today(), account=body.account, amount=line.net_pay,
                   party=emp.full_name, reference=body.reference, note=body.note or f"Salary {run.month}", proof_id=body.proof_id,
                   no_proof_reason=body.no_proof_reason, employee_id=emp.id, payroll_line_id=line.id)
    db.add(e)
    db.flush()
    if body.proof_id:
        _attach(db, actor, [body.proof_id], "money_entries", e.id)
    posting.money_entry(db, actor.branch, e)
    db.flush()
    paid_ids = set(db.scalars(select(MoneyEntry.payroll_line_id).where(MoneyEntry.payroll_line_id.in_([l.id for l in run.lines]), MoneyEntry.status == "posted")))
    if all(l.net_pay <= 0 or l.id in paid_ids for l in run.lines):
        run.status = "paid"
    db.commit()
    return run_out(db, run)
