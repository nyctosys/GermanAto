"""Double-entry posting. Every business event calls post() with the lines it
produces; an entry that does not balance is refused, and entries are never
edited, only reversed (spec D3)."""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Branch, JournalEntry, JournalLine, LedgerAccount, PeriodClose
from app.numbering import next_number
from app.config import local_today

CENT = Decimal("0.01")

CHART: tuple[tuple[str, str, str], ...] = (
    ("1010", "Cash in hand", "asset"), ("1020", "Bank account", "asset"), ("1030", "Mobile wallet", "asset"),
    ("1100", "Receivables", "asset"), ("1200", "Inventory", "asset"), ("1300", "Employee advances", "asset"),
    ("2000", "Payables to vendors", "liability"), ("2100", "Goods received not billed", "liability"),
    ("2200", "Customer advances", "liability"), ("2300", "Sales tax payable", "liability"), ("2400", "Salaries payable", "liability"),
    ("3000", "Owner capital", "equity"), ("3100", "Owner drawings", "equity"), ("3900", "Opening balance equity", "equity"),
    ("4000", "Revenue: labour", "revenue"), ("4100", "Revenue: parts", "revenue"), ("4900", "Other income", "revenue"),
    ("5000", "Cost of parts sold", "expense"), ("6000", "Operating expenses", "expense"), ("6100", "Salaries and wages", "expense"),
    ("6200", "Freight and purchase adjustments", "expense"), ("6900", "Stock write-offs and corrections", "expense"),
    ("6910", "Cash over and short", "expense"),
)
MONEY_CODE = {"cash": "1010", "bank": "1020", "wallet": "1030"}


class JournalError(ValueError):
    pass


@dataclass(frozen=True)
class Line:
    code: str
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)
    category_id: uuid.UUID | None = None
    note: str = ""


def q(v: Decimal) -> Decimal:
    return Decimal(v).quantize(CENT, ROUND_HALF_UP)


def closed_period(db: Session, branch: Branch, on: date) -> str | None:
    """The label of the closed month or year that contains this date, if there is one."""
    row = db.execute(select(PeriodClose.kind, PeriodClose.period).where(
        PeriodClose.branch_id == branch.id, PeriodClose.status == "closed",
        ((PeriodClose.kind == "month") & (PeriodClose.period == on.strftime("%Y-%m"))) | ((PeriodClose.kind == "year") & (PeriodClose.period == str(on.year))))).first()
    if not row:
        return None
    return on.strftime("%B %Y") if row[0] == "month" else str(on.year)


def ensure_chart(db: Session, branch: Branch) -> dict[str, LedgerAccount]:
    have = {a.code: a for a in db.scalars(select(LedgerAccount).where(LedgerAccount.branch_id == branch.id))}
    missing = [c for c in CHART if c[0] not in have]
    for code, name, kind in missing:
        a = LedgerAccount(code=code, name=name, type=kind, branch_id=branch.id)
        db.add(a)
        have[code] = a
    if missing:
        db.flush()
    return have


def post(db: Session, branch: Branch, memo: str, lines: list[Line], *, on: date | None = None,
         source: tuple[str, uuid.UUID] | None = None, reverses: JournalEntry | None = None) -> JournalEntry | None:
    """Posts one balanced entry. Zero lines are dropped; an entry that is all zeros posts nothing."""
    lines = [Line(l.code, q(l.debit), q(l.credit), l.category_id, l.note) for l in lines]
    if any(l.debit < 0 or l.credit < 0 or (l.debit and l.credit) for l in lines):
        raise JournalError("A journal line is either a debit or a credit, and never negative")
    lines = [l for l in lines if l.debit or l.credit]
    if not lines:
        return None
    if len(lines) < 2:
        raise JournalError("A journal entry needs at least two lines")
    debit, credit = sum((l.debit for l in lines), Decimal(0)), sum((l.credit for l in lines), Decimal(0))
    if debit != credit:
        raise JournalError(f"Unbalanced entry for {memo!r}: debits {debit} and credits {credit}")
    closed = closed_period(db, branch, on or local_today())
    if closed:
        raise JournalError(f"{closed} is closed, so nothing can be recorded in it. Record it today instead, or ask an admin to reopen the month.")
    chart = ensure_chart(db, branch)
    unknown = {l.code for l in lines} - set(chart)
    if unknown:
        raise JournalError(f"Unknown ledger account {sorted(unknown)}")
    entry = JournalEntry(number=next_number(db, branch, "journal"), entry_date=on or local_today(), memo=memo[:300], branch_id=branch.id,
                         source_type=source[0] if source else None, source_id=source[1] if source else None,
                         reverses_id=reverses.id if reverses else None,
                         lines=[JournalLine(position=n, ledger_account_id=chart[l.code].id, debit=l.debit, credit=l.credit,
                                            category_id=l.category_id, note=l.note) for n, l in enumerate(lines)])
    db.add(entry)
    db.flush()
    return entry


def reverse(db: Session, branch: Branch, entry: JournalEntry, memo: str, on: date | None = None) -> JournalEntry:
    """A mirror of the entry: every debit becomes a credit. An entry can be reversed once."""
    if db.scalar(select(JournalEntry.id).where(JournalEntry.reverses_id == entry.id)):
        raise JournalError(f"{entry.number} has already been reversed")
    codes = {a.id: a.code for a in db.scalars(select(LedgerAccount).where(LedgerAccount.branch_id == branch.id))}
    mirrored = [Line(codes[l.ledger_account_id], debit=l.credit, credit=l.debit, category_id=l.category_id, note=l.note) for l in entry.lines]
    return post(db, branch, memo, mirrored, on=on, source=(entry.source_type, entry.source_id) if entry.source_type else None, reverses=entry)


def live_entry(db: Session, source_type: str, source_id: uuid.UUID) -> JournalEntry | None:
    """The latest entry for a source that has not been reversed."""
    reversed_ids = select(JournalEntry.reverses_id).where(JournalEntry.reverses_id.is_not(None))
    return db.scalar(select(JournalEntry).where(JournalEntry.source_type == source_type, JournalEntry.source_id == source_id,
                                                JournalEntry.reverses_id.is_(None), JournalEntry.id.not_in(reversed_ids))
                     .order_by(JournalEntry.created_at.desc()))


def balances(db: Session, branch: Branch, *, as_of: date | None = None, since: date | None = None) -> dict[str, tuple[Decimal, Decimal]]:
    """Debit and credit totals per ledger account code."""
    stmt = (select(LedgerAccount.code, func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0))
            .select_from(LedgerAccount).outerjoin(JournalLine, JournalLine.ledger_account_id == LedgerAccount.id)
            .outerjoin(JournalEntry, JournalEntry.id == JournalLine.entry_id).where(LedgerAccount.branch_id == branch.id)
            .group_by(LedgerAccount.code))
    if as_of:
        stmt = stmt.where((JournalEntry.entry_date <= as_of) | (JournalEntry.id.is_(None)))
    if since:
        stmt = stmt.where((JournalEntry.entry_date >= since) | (JournalEntry.id.is_(None)))
    return {code: (d, c) for code, d, c in db.execute(stmt)}


def money_balance(db: Session, branch: Branch, kind: str) -> Decimal:
    d, c = balances(db, branch).get(MONEY_CODE[kind], (Decimal(0), Decimal(0)))
    return d - c


def sync_opening(db: Session, branch: Branch, account: Account) -> None:
    """Keeps the journal's opening entry for a money account equal to its opening balance."""
    current = live_entry(db, "account_opening", account.id)
    if current:
        total = next((l.debit for l in current.lines if l.debit), Decimal(0))
        if total == account.opening_balance and current.entry_date == account.opening_date:
            return
        reverse(db, branch, current, f"Opening balance of {account.name} corrected")
    if account.opening_balance > 0:
        post(db, branch, f"Opening balance of {account.name}",
             [Line(MONEY_CODE[account.kind], debit=account.opening_balance), Line("3900", credit=account.opening_balance)],
             on=account.opening_date, source=("account_opening", account.id))


def category_totals(db: Session, branch: Branch, start: date, end: date) -> dict:
    """Operating expenses by category for a period (debits less credits on 'Operating expenses')."""
    from app.models import ExpenseCategory
    rows = db.execute(select(JournalLine.category_id, func.sum(JournalLine.debit - JournalLine.credit))
                      .join(JournalEntry, JournalEntry.id == JournalLine.entry_id).join(LedgerAccount, LedgerAccount.id == JournalLine.ledger_account_id)
                      .where(JournalEntry.branch_id == branch.id, LedgerAccount.code == "6000", JournalEntry.entry_date >= start, JournalEntry.entry_date <= end)
                      .group_by(JournalLine.category_id)).all()
    names = {c.id: c.name for c in db.scalars(select(ExpenseCategory).where(ExpenseCategory.branch_id == branch.id))}
    return {names.get(cid, "Uncategorised"): total for cid, total in rows if total}


def money_movement(db: Session, branch: Branch, start: date, end: date) -> dict:
    """Per money account: what came in and went out in the period, by the kind of event behind it."""
    rows = db.execute(select(LedgerAccount.code, JournalEntry.source_type, func.sum(JournalLine.debit), func.sum(JournalLine.credit))
                      .join(JournalLine, JournalLine.ledger_account_id == LedgerAccount.id).join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
                      .where(JournalEntry.branch_id == branch.id, LedgerAccount.code.in_(list(MONEY_CODE.values())),
                             JournalEntry.entry_date >= start, JournalEntry.entry_date <= end)
                      .group_by(LedgerAccount.code, JournalEntry.source_type)).all()
    kinds = {v: k for k, v in MONEY_CODE.items()}
    out: dict = {k: {"in": Decimal(0), "out": Decimal(0), "in_by_source": {}, "out_by_source": {}} for k in MONEY_CODE}
    for code, source, debit, credit in rows:
        a = out[kinds[code]]
        label = source or "other"
        if debit:
            a["in"] += debit
            a["in_by_source"][label] = a["in_by_source"].get(label, Decimal(0)) + debit
        if credit:
            a["out"] += credit
            a["out_by_source"][label] = a["out_by_source"].get(label, Decimal(0)) + credit
    return out
