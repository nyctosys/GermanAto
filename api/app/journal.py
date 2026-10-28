"""Double-entry posting. Every business event calls post() with the lines it
produces; an entry that does not balance is refused, and entries are never
edited, only reversed (spec D3)."""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Branch, JournalEntry, JournalLine, LedgerAccount
from app.numbering import next_number

CENT = Decimal("0.01")

CHART: tuple[tuple[str, str, str], ...] = (
    ("1010", "Cash in hand", "asset"), ("1020", "Bank account", "asset"), ("1030", "Mobile wallet", "asset"),
    ("1100", "Receivables", "asset"), ("1200", "Inventory", "asset"),
    ("2000", "Payables to vendors", "liability"), ("2100", "Goods received not billed", "liability"),
    ("2200", "Customer advances", "liability"), ("2300", "Sales tax payable", "liability"), ("2400", "Salaries payable", "liability"),
    ("3000", "Owner capital", "equity"), ("3100", "Owner drawings", "equity"), ("3900", "Opening balance equity", "equity"),
    ("4000", "Revenue: labour", "revenue"), ("4100", "Revenue: parts", "revenue"), ("4900", "Other income", "revenue"),
    ("5000", "Cost of parts sold", "expense"), ("6000", "Operating expenses", "expense"), ("6100", "Salaries and wages", "expense"),
    ("6200", "Freight and purchase adjustments", "expense"), ("6900", "Stock write-offs and corrections", "expense"),
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
    chart = ensure_chart(db, branch)
    unknown = {l.code for l in lines} - set(chart)
    if unknown:
        raise JournalError(f"Unknown ledger account {sorted(unknown)}")
    entry = JournalEntry(number=next_number(db, branch, "journal"), entry_date=on or date.today(), memo=memo[:300], branch_id=branch.id,
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
