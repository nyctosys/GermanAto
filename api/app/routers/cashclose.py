"""Daily cash close: count each account, compare it with what the books say, sign off.

Urgent money may still be recorded after a day is signed. The original close stays; a later
sequence recounts the books (post-closing close) once the new activity is counted.
"""

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
from app.models import Account, CashClose, JournalEntry, JournalLine, LedgerAccount, User
from app.money_setup import ensure_money_setup
from app.validators import Text
from app.config import local_today

router = APIRouter(prefix="/api", tags=["cash close"])
can_close = require("cash-close")
KINDS = ("cash", "bank", "wallet")


def can_see(actor: Actor = Depends(current_actor)) -> Actor:
    if not any(actor.can(p) for p in ("cash-close", "reports-finance")):
        raise HTTPException(403, "You don't have permission to do this")
    return actor


def last_close(db: Session, actor: Actor, kind: str) -> CashClose | None:
    return db.scalar(select(CashClose).where(CashClose.branch_id == actor.branch.id, CashClose.account == kind)
                     .order_by(CashClose.close_date.desc(), CashClose.sequence.desc()).limit(1))


def closes_on(db: Session, actor: Actor, kind: str, on: date) -> list[CashClose]:
    return list(db.scalars(select(CashClose).where(
        CashClose.branch_id == actor.branch.id, CashClose.account == kind, CashClose.close_date == on)
        .order_by(CashClose.sequence)))


def balance_on(db: Session, branch, kind: str, on: date) -> Decimal:
    d, c = journal.balances(db, branch, as_of=on).get(journal.MONEY_CODE[kind], (Decimal(0), Decimal(0)))
    return d - c


def next_close_date(last: date | None, today: date) -> date | None:
    """The next new day this account should be signed. None means already closed through today
    (a post-closing recount may still be needed if money moved after the last sign)."""
    if last is None:
        return today
    nxt = last + timedelta(days=1)
    return None if nxt > today else nxt


def accounts_closed_on(db: Session, branch_id, accounts: set, on: date) -> list[str]:
    """Which of the given accounts already have at least one signed count for this day."""
    kinds = {a for a in accounts if a in KINDS}
    if not kinds:
        return []
    rows = db.scalars(select(CashClose.account).where(
        CashClose.branch_id == branch_id, CashClose.account.in_(kinds), CashClose.close_date == on).distinct())
    return sorted(set(rows))


def assert_day_open(db: Session, branch_id, accounts: set, on: date) -> list[str]:
    """Formerly blocked posting on a signed day. Now allows it and returns the accounts already closed
    so callers can warn that this is a post-closing transaction."""
    return accounts_closed_on(db, branch_id, accounts - {None}, on)


def close_out(c: CashClose, by: str | None) -> dict:
    return {"id": c.id, "account": c.account, "close_date": c.close_date, "sequence": c.sequence,
            "expected": c.expected, "counted": c.counted, "difference": c.difference, "reason": c.reason,
            "note": c.note, "closed_by": by, "created_at": c.created_at,
            "post_closing": c.sequence > 1}


def movements_since(db: Session, actor: Actor, kind: str, since) -> list[dict]:
    """Journal lines on this money account after a close was signed (timestamps for the audit trail)."""
    code = journal.MONEY_CODE[kind]
    rows = db.execute(
        select(JournalEntry, JournalLine)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .join(LedgerAccount, LedgerAccount.id == JournalLine.ledger_account_id)
        .where(JournalEntry.branch_id == actor.branch.id, LedgerAccount.code == code,
               JournalEntry.created_at > since)
        .order_by(JournalEntry.created_at, JournalLine.position)
    ).all()
    out = []
    for entry, line in rows:
        # Asset accounts: debit increases cash in hand / bank / wallet.
        delta = line.debit - line.credit
        if delta == 0:
            continue
        out.append({
            "at": entry.created_at, "entry_date": entry.entry_date, "memo": entry.memo,
            "amount": delta, "source_type": entry.source_type, "source_id": entry.source_id,
            "number": entry.number,
        })
    return out


def post_closing_detail(db: Session, actor: Actor, kind: str, by_name: str | None = None) -> dict | None:
    """If today was signed and money moved afterwards, return original close / movements / books now."""
    today = local_today()
    rows = closes_on(db, actor, kind, today)
    if not rows:
        return None
    latest = rows[-1]
    moves = movements_since(db, actor, kind, latest.created_at)
    books = journal.money_balance(db, actor.branch, kind)
    if not moves and books == latest.counted:
        return None
    first = rows[0]
    return {
        "needed": True,
        "original": {
            "sequence": first.sequence, "expected": first.expected, "counted": first.counted,
            "difference": first.difference, "at": first.created_at, "closed_by": by_name,
        },
        "prior_closes": [
            {"sequence": c.sequence, "expected": c.expected, "counted": c.counted,
             "difference": c.difference, "at": c.created_at} for c in rows
        ],
        "movements": moves,
        "books_now": books,
        "last_signed": latest.counted,
        "change_since_sign": books - latest.counted,
    }


def day_sign_state(db: Session, actor: Actor, account: str, on: date) -> dict:
    """Whether this account can be signed for `on` (first close, gap-fill, or post-closing recount)."""
    rows = closes_on(db, actor, account, on)
    already = bool(rows)
    later = db.scalar(select(func.max(CashClose.close_date)).where(
        CashClose.branch_id == actor.branch.id, CashClose.account == account))
    last = last_close(db, actor, account)
    nxt = next_close_date(last.close_date if last else None, local_today())
    gap = bool(later and later > on and not already)
    post_closing = False
    if already and on == local_today():
        latest = rows[-1]
        books = journal.money_balance(db, actor.branch, account)
        moves = movements_since(db, actor, account, latest.created_at)
        post_closing = bool(moves) or books != latest.counted
    if post_closing:
        can_sign = True
    elif already:
        can_sign = False
    elif gap or nxt == on or (last is None and on <= local_today()):
        can_sign = True
    elif nxt and nxt < on:
        can_sign = False
    else:
        can_sign = False
    return {
        "already_closed": already,
        "gap_fill": gap,
        "post_closing": post_closing,
        "later_through": later if later and later > on else None,
        "can_sign": can_sign,
        "must_close_first": nxt.isoformat() if (nxt and nxt < on and not gap and not already) else None,
        "close_count": len(rows),
    }


@router.get("/cash-closes/status")
def status(actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    """For each account: books now, last signed count, catch-up day, and post-closing recount if needed."""
    ensure_money_setup(db, actor.branch)
    db.commit()
    today = local_today()
    names = {a.kind: a.name for a in db.scalars(select(Account).where(Account.branch_id == actor.branch.id))}
    out = []
    for kind in KINDS:
        last = last_close(db, actor, kind)
        nxt = next_close_date(last.close_date if last else None, today)
        by = db.get(User, last.created_by).full_name if last and last.created_by else None
        detail = post_closing_detail(db, actor, kind, by)
        closed_today = bool(last and last.close_date == today)
        out.append({
            "account": kind, "name": names[kind],
            "expected": journal.money_balance(db, actor.branch, kind),
            "last_close": last and {
                "close_date": last.close_date, "sequence": last.sequence, "counted": last.counted,
                "difference": last.difference, "at": last.created_at, "closed_by": by,
            },
            "closed_today": closed_today and not (detail and detail["needed"]),
            "signed_today": closed_today,
            "next_close_date": nxt,
            "expected_on_next": balance_on(db, actor.branch, kind, nxt) if nxt else None,
            "days_behind": (today - nxt).days if nxt and nxt < today else 0,
            "may_close_earlier": last is None and nxt == today,
            "post_closing": detail,
        })
    return out


@router.get("/cash-closes/expected")
def expected_for_day(account: Literal["cash", "bank", "wallet"], on: date,
                     actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    """Books balance for one account at the end of a day — used when catching up or post-closing."""
    if on > local_today():
        raise HTTPException(422, "A day can't be closed before it has happened")
    ensure_money_setup(db, actor.branch)
    db.commit()
    return {
        "account": account, "close_date": on, "expected": balance_on(db, actor.branch, account, on)
        if on < local_today() else journal.money_balance(db, actor.branch, account),
        **day_sign_state(db, actor, account, on),
    }


def _month_end(year: int, month: int) -> date:
    return date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1) - timedelta(days=1)


def _account_had_movement(db: Session, branch, kind: str, start: date, end: date) -> bool:
    code = journal.MONEY_CODE[kind]
    d, c = journal.balances(db, branch, since=start, as_of=end).get(code, (Decimal(0), Decimal(0)))
    return bool(d or c)


def missed_dates_for_account(db: Session, actor: Actor, kind: str) -> set[date]:
    """Days with no signed count that were skipped (gaps between closes, or month-ends jumped over)."""
    closes = sorted({c.close_date for c in db.scalars(
        select(CashClose).where(CashClose.branch_id == actor.branch.id, CashClose.account == kind))})
    missed: set[date] = set()
    today = local_today()
    for a, b in zip(closes, closes[1:]):
        d = a + timedelta(days=1)
        while d < b:
            missed.add(d)
            d += timedelta(days=1)
    if not closes:
        return missed
    latest = closes[-1]
    y, m = latest.year, latest.month
    for _ in range(24):
        end = _month_end(y, m)
        start = date(y, m, 1)
        if end < latest and end not in closes and end < today:
            if _account_had_movement(db, actor.branch, kind, start, end):
                missed.add(end)
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        if date(y, m, 1) < date(latest.year, latest.month, 1) - timedelta(days=400):
            break
    return {d for d in missed if d < today}


@router.get("/cash-closes/missed")
def missed_closes(actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    """Days that still need a first signed count (skipped gaps or unsigned month-ends), newest first."""
    ensure_money_setup(db, actor.branch)
    db.commit()
    names = {a.kind: a.name for a in db.scalars(select(Account).where(Account.branch_id == actor.branch.id))}
    by_day: dict[date, list[str]] = {}
    for kind in KINDS:
        for d in missed_dates_for_account(db, actor, kind):
            by_day.setdefault(d, []).append(kind)
    out = []
    for d in sorted(by_day.keys(), reverse=True)[:60]:
        accounts = [k for k in KINDS if k in by_day[d]]
        lines = [{"account": k, "name": names[k], "expected": balance_on(db, actor.branch, k, d)} for k in accounts]
        out.append({
            "date": d, "accounts": accounts, "names": [names[k] for k in accounts],
            "lines": lines, "total": sum((line["expected"] for line in lines), Decimal(0)),
        })
    return out


@router.get("/cash-closes")
def history(account: Literal["cash", "bank", "wallet"] | None = None, limit: int = Query(60, ge=1, le=300),
            actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    stmt = select(CashClose, User.full_name).outerjoin(User, User.id == CashClose.created_by).where(CashClose.branch_id == actor.branch.id) \
        .order_by(CashClose.close_date.desc(), CashClose.sequence.desc(), CashClose.created_at.desc()).limit(limit)
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
    """Signs the count for a day (first close, gap-fill, or post-closing recount)."""
    day = body.close_date or local_today()
    if day > local_today():
        raise HTTPException(422, "A day can't be closed before it has happened")
    state = day_sign_state(db, actor, body.account, day)
    if not state["can_sign"]:
        if state["already_closed"] and not state["post_closing"]:
            raise HTTPException(409, "This account is already closed for that day")
        if state["must_close_first"]:
            raise HTTPException(409, f"Close {date.fromisoformat(state['must_close_first']):%d %b %Y} for this account first.")
        raise HTTPException(409, "This day can't be signed for this account.")
    gap = state["gap_fill"]
    post_closing = state["post_closing"]
    seq = state["close_count"] + 1
    if day < local_today() or gap:
        expected = balance_on(db, actor.branch, body.account, day)
    else:
        expected = journal.money_balance(db, actor.branch, body.account)
    diff = body.counted - expected
    if diff != 0 and len(body.reason) < 5:
        raise HTTPException(422, f"The count is {abs(diff):,.2f} {'over' if diff > 0 else 'short'}. Say why before signing.")
    # Gap fill: record the signature without moving later locked books.
    # Post-closing and normal closes post a difference so the books match the drawer.
    post_diff = Decimal(0) if gap else diff
    note = body.note
    if post_closing and not note:
        note = "Post-closing recount after urgent transactions"
    cc = CashClose(account=body.account, close_date=day, sequence=seq, expected=expected, counted=body.counted,
                   difference=diff, reason=body.reason if diff else "", note=note)
    db.add(cc)
    db.flush()
    if post_diff:
        posting.cash_difference(db, actor.branch, body.account, post_diff, day, cc.id)
    db.commit()
    return close_out(cc, actor.user.full_name)
