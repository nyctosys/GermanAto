"""Read-only views of the journal: the trial balance and the entries behind it."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import journal
from app.auth import Actor, require
from app.db import get_db
from app.models import ExpenseCategory, JournalEntry, JournalLine, LedgerAccount

router = APIRouter(prefix="/api/journal", tags=["journal"])
can_see = require("reports-finance")


@router.get("/trial-balance")
def trial_balance(as_of: date | None = None, actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    """Every ledger account with its debits and credits. The two totals must always be equal."""
    journal.ensure_chart(db, actor.branch)
    db.commit()
    totals = journal.balances(db, actor.branch, as_of=as_of)
    rows = []
    for a in db.scalars(select(LedgerAccount).where(LedgerAccount.branch_id == actor.branch.id).order_by(LedgerAccount.code)):
        d, c = totals.get(a.code, (Decimal(0), Decimal(0)))
        rows.append({"code": a.code, "name": a.name, "type": a.type, "debit": d, "credit": c, "balance": d - c})
    debit, credit = sum((r["debit"] for r in rows), Decimal(0)), sum((r["credit"] for r in rows), Decimal(0))
    return {"as_of": as_of, "rows": rows, "debit": debit, "credit": credit, "balanced": debit == credit}


def _chart_and_cats(db: Session, branch_id: uuid.UUID):
    chart = {a.id: a for a in db.scalars(select(LedgerAccount).where(LedgerAccount.branch_id == branch_id))}
    cats = {c.id: c.name for c in db.scalars(select(ExpenseCategory).where(ExpenseCategory.branch_id == branch_id))}
    return chart, cats


@router.get("/entries")
def entries(source_type: str | None = None, source_id: uuid.UUID | None = None,
            date_from: date | None = None, date_to: date | None = None,
            limit: int = Query(100, ge=1, le=5000),
            actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must be on or before date_to")
    stmt = (select(JournalEntry).where(JournalEntry.branch_id == actor.branch.id)
            .options(selectinload(JournalEntry.lines))
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc()).limit(limit))
    if source_type:
        stmt = stmt.where(JournalEntry.source_type == source_type)
    if source_id:
        stmt = stmt.where(JournalEntry.source_id == source_id)
    if date_from:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    chart, cats = _chart_and_cats(db, actor.branch.id)
    return [{"id": e.id, "number": e.number, "date": e.entry_date, "memo": e.memo, "source_type": e.source_type, "source_id": e.source_id,
             "reverses_id": e.reverses_id,
             "lines": [{"code": chart[l.ledger_account_id].code, "name": chart[l.ledger_account_id].name, "debit": l.debit, "credit": l.credit,
                        "category": cats.get(l.category_id)} for l in e.lines]} for e in db.scalars(stmt)]


@router.get("/ledger")
def ledger(date_from: date = Query(...), date_to: date = Query(...),
           limit: int = Query(5000, ge=1, le=10000),
           actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    """One row per journal line for the period — the month ledger for Excel and the Journal tab."""
    if date_from > date_to:
        raise HTTPException(422, "date_from must be on or before date_to")
    chart, cats = _chart_and_cats(db, actor.branch.id)
    stmt = (select(JournalLine, JournalEntry)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(JournalEntry.branch_id == actor.branch.id,
                   JournalEntry.entry_date >= date_from, JournalEntry.entry_date <= date_to)
            .order_by(JournalEntry.entry_date, JournalEntry.number, JournalLine.position)
            .limit(limit))
    rows = []
    debit = credit = Decimal(0)
    for line, entry in db.execute(stmt):
        acct = chart[line.ledger_account_id]
        debit += line.debit
        credit += line.credit
        rows.append({
            "date": entry.entry_date, "entry_number": entry.number, "memo": entry.memo,
            "source_type": entry.source_type, "account_code": acct.code, "account_name": acct.name,
            "debit": line.debit, "credit": line.credit, "category": cats.get(line.category_id),
        })
    return {"from": date_from, "to": date_to, "rows": rows, "debit": debit, "credit": credit, "truncated": len(rows) >= limit}
