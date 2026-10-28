"""Read-only views of the journal: the trial balance and the entries behind it."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import journal
from app.auth import Actor, require
from app.db import get_db
from app.models import ExpenseCategory, JournalEntry, LedgerAccount

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


@router.get("/entries")
def entries(source_type: str | None = None, source_id: uuid.UUID | None = None, limit: int = Query(100, ge=1, le=500),
            actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    stmt = select(JournalEntry).where(JournalEntry.branch_id == actor.branch.id).order_by(JournalEntry.created_at.desc()).limit(limit)
    if source_type:
        stmt = stmt.where(JournalEntry.source_type == source_type)
    if source_id:
        stmt = stmt.where(JournalEntry.source_id == source_id)
    chart = {a.id: a for a in db.scalars(select(LedgerAccount).where(LedgerAccount.branch_id == actor.branch.id))}
    cats = {c.id: c.name for c in db.scalars(select(ExpenseCategory).where(ExpenseCategory.branch_id == actor.branch.id))}
    return [{"id": e.id, "number": e.number, "date": e.entry_date, "memo": e.memo, "source_type": e.source_type, "source_id": e.source_id,
             "reverses_id": e.reverses_id,
             "lines": [{"code": chart[l.ledger_account_id].code, "name": chart[l.ledger_account_id].name, "debit": l.debit, "credit": l.credit,
                        "category": cats.get(l.category_id)} for l in e.lines]} for e in db.scalars(stmt)]
