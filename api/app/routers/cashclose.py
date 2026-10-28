"""Daily cash close: count each account, compare it with what the books say, sign off."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import journal, posting
from app.auth import Actor, current_actor, require
from app.db import get_db
from app.models import Account, CashClose, User
from app.money_setup import ensure_money_setup
from app.numbering import next_number
from app.validators import Text

router = APIRouter(prefix="/api", tags=["cash close"])
can_close = require("cash-close")
KINDS = ("cash", "bank", "wallet")


def can_see(actor: Actor = Depends(current_actor)) -> Actor:
    if not any(actor.can(p) for p in ("cash-close", "reports-finance")):
        raise HTTPException(403, "You don't have permission to do this")
    return actor


def last_close(db: Session, actor: Actor, kind: str) -> CashClose | None:
    return db.scalar(select(CashClose).where(CashClose.branch_id == actor.branch.id, CashClose.account == kind)
                     .order_by(CashClose.close_date.desc()).limit(1))


def assert_day_open(db: Session, branch_id, accounts: set, on: date) -> None:
    """A signed count is final: nothing may be recorded or voided on a day that account has already closed."""
    hit = db.scalar(select(func.max(CashClose.close_date)).where(CashClose.branch_id == branch_id, CashClose.account.in_(accounts - {None}),
                                                                 CashClose.close_date >= on))
    if hit:
        raise HTTPException(409, f"The books for {on:%d %b %Y} are closed (counted and signed on {hit:%d %b %Y}). Record it today instead.")


def close_out(c: CashClose, by: str | None) -> dict:
    return {"id": c.id, "account": c.account, "close_date": c.close_date, "expected": c.expected, "counted": c.counted,
            "difference": c.difference, "reason": c.reason, "note": c.note, "closed_by": by, "created_at": c.created_at}


@router.get("/cash-closes/status")
def status(actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    """For each account: what the books say now, and the last signed count."""
    ensure_money_setup(db, actor.branch)
    db.commit()
    names = {a.kind: a.name for a in db.scalars(select(Account).where(Account.branch_id == actor.branch.id))}
    out = []
    for kind in KINDS:
        last = last_close(db, actor, kind)
        out.append({"account": kind, "name": names[kind], "expected": journal.money_balance(db, actor.branch, kind),
                    "last_close": last and {"close_date": last.close_date, "counted": last.counted, "difference": last.difference},
                    "closed_today": bool(last and last.close_date == date.today())})
    return out


@router.get("/cash-closes")
def history(account: Literal["cash", "bank", "wallet"] | None = None, limit: int = Query(60, ge=1, le=300),
            actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    stmt = select(CashClose, User.full_name).outerjoin(User, User.id == CashClose.created_by).where(CashClose.branch_id == actor.branch.id) \
        .order_by(CashClose.close_date.desc(), CashClose.created_at.desc()).limit(limit)
    if account:
        stmt = stmt.where(CashClose.account == account)
    return [close_out(c, by) for c, by in db.execute(stmt)]


class CloseIn(BaseModel):
    account: Literal["cash", "bank", "wallet"]
    close_date: date | None = None
    counted: Decimal = Field(ge=0, le=10_000_000_000, decimal_places=2)
    reason: Text = Field(default="", max_length=500)
    note: Text = Field(default="", max_length=500)


@router.post("/cash-closes", status_code=201)
def close(body: CloseIn, actor: Actor = Depends(can_close), db: Session = Depends(get_db)):
    """Signs the count for a day. The expected figure is worked out from the journal up to the end of that day."""
    day = body.close_date or date.today()
    if day > date.today():
        raise HTTPException(422, "A day can't be closed before it has happened")
    if db.scalar(select(CashClose.id).where(CashClose.branch_id == actor.branch.id, CashClose.account == body.account, CashClose.close_date == day)):
        raise HTTPException(409, "This account is already closed for that day")
    later = db.scalar(select(func.max(CashClose.close_date)).where(CashClose.branch_id == actor.branch.id, CashClose.account == body.account))
    if later and later > day:
        raise HTTPException(409, f"This account was already closed up to {later:%d %b %Y}. Close the days in order.")
    d, c = journal.balances(db, actor.branch, as_of=day).get(journal.MONEY_CODE[body.account], (Decimal(0), Decimal(0)))
    expected = d - c
    diff = body.counted - expected
    if diff != 0 and len(body.reason) < 5:
        raise HTTPException(422, f"The count is {abs(diff):,.2f} {'over' if diff > 0 else 'short'}. Say why before signing.")
    cc = CashClose(account=body.account, close_date=day, expected=expected, counted=body.counted, difference=diff, reason=body.reason if diff else "",
                   note=body.note)
    db.add(cc)
    db.flush()
    if diff:
        posting.cash_difference(db, actor.branch, body.account, diff, day, cc.id)
    db.commit()
    return close_out(cc, actor.user.full_name)
