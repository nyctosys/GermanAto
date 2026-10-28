"""Money In and Money Out (spec R12, R13): one page each for every incoming and
outgoing payment, whatever its source, plus the entries that aren't tied to a
customer or vendor document."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import posting
from app.auth import Actor, current_actor
from app.db import get_db
from app.models import Customer, ExpenseCategory, Invoice, MoneyEntry, Payment, User, Vendor, VendorPayment
from app.numbering import next_number
from app.routers.cashclose import assert_day_open
from app.routers.estimates import Proof
from app.routers.workshop import _attach
from app.validators import Text

router = APIRouter(prefix="/api", tags=["money"])

IN_KINDS = ("other_income", "owner_capital")
# Who may record which kind: money in needs payments-in, spending needs expenses, and the owner's
# own money movements (drawings, transfers) need payments-out.
NEEDS = {"refund": "advance-refund", "other_income": "payments-in", "owner_capital": "payments-in", "expense": "expenses", "drawings": "payments-out", "transfer": "payments-out"}
IN_SOURCES = ("invoice_payment", "advance", "other_income", "owner_capital", "transfer")
OUT_SOURCES = ("vendor_payment", "expense", "drawings", "transfer", "refund")


def see_money(actor: Actor = Depends(current_actor)) -> Actor:
    if not any(actor.can(p) for p in ("payments-in", "payments-out", "expenses", "reports-finance")):
        raise HTTPException(403, "You don't have permission to do this")
    return actor


class EntryIn(Proof):
    kind: Literal["other_income", "owner_capital", "transfer", "expense", "drawings"]
    amount: Decimal = Field(gt=0, le=10_000_000_000, decimal_places=2)
    account: Literal["cash", "bank", "wallet"]
    to_account: Literal["cash", "bank", "wallet"] | None = None
    category_id: uuid.UUID | None = None
    party: Text = Field(default="", max_length=120)
    reference: Text = Field(default="", max_length=60)
    note: Text = Field(default="", max_length=500)
    occurred_on: date | None = None

    @model_validator(mode="after")
    def kind_rules(self):
        if self.kind == "transfer":
            if not self.to_account or self.to_account == self.account:
                raise ValueError("A transfer goes from one account to a different one")
        elif self.to_account:
            raise ValueError("Only a transfer has a destination account")
        if (self.kind == "expense") != bool(self.category_id):
            raise ValueError("Pick a category for an expense, and only for an expense")
        return self


def entry_out(db: Session, e: MoneyEntry) -> dict:
    return {"id": e.id, "number": e.number, "kind": e.kind, "status": e.status, "occurred_on": e.occurred_on, "account": e.account,
            "to_account": e.to_account, "amount": e.amount, "party": e.party, "reference": e.reference, "note": e.note,
            "category_id": e.category_id, "proof_url": f"/api/attachments/{e.proof_id}/file" if e.proof_id else None,
            "no_proof_reason": e.no_proof_reason, "void_reason": e.void_reason}


@router.post("/money-entries", status_code=201)
def record_entry(body: EntryIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    if not actor.can(NEEDS[body.kind]):
        raise HTTPException(403, "You don't have permission to do this")
    when = body.occurred_on or date.today()
    if when > date.today():
        raise HTTPException(422, "The date is in the future")
    assert_day_open(db, actor.branch.id, {body.account, body.to_account}, when)
    touched = {body.account, body.to_account} - {None, "cash"}
    if touched and not body.reference and not body.proof_id:
        raise HTTPException(422, "Add the transaction reference or a screenshot for a bank or wallet movement")
    if body.category_id:
        cat = db.get(ExpenseCategory, body.category_id)
        if not cat or cat.branch_id != actor.branch.id:
            raise HTTPException(404, "Category not found")
        if not cat.is_active:
            raise HTTPException(422, f"{cat.name} is retired. Pick another category.")
    e = MoneyEntry(number=next_number(db, actor.branch, body.kind), occurred_on=when,
                   **body.model_dump(exclude={"occurred_on"}))
    db.add(e)
    db.flush()
    if body.proof_id:
        _attach(db, actor, [body.proof_id], "money_entries", e.id)
    posting.money_entry(db, actor.branch, e)
    db.commit()
    return entry_out(db, e)


class VoidIn(BaseModel):
    reason: Text = Field(min_length=3, max_length=500)


@router.post("/money-entries/{entry_id}/void")
def void_entry(entry_id: uuid.UUID, body: VoidIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    e = db.scalar(select(MoneyEntry).where(MoneyEntry.id == entry_id).with_for_update())
    if not e or e.branch_id != actor.branch.id:
        raise HTTPException(404, "Entry not found")
    if not actor.can(NEEDS[e.kind]) and not (e.kind == "refund" and actor.can("credit-notes")):
        raise HTTPException(403, "You don't have permission to do this")
    if e.status != "posted":
        raise HTTPException(409, "Already voided")
    assert_day_open(db, actor.branch.id, {e.account, e.to_account}, e.occurred_on)
    if e.payment_id:  # a voided refund means the advance is still held
        db.get(Payment, e.payment_id).refunded = False
    e.status, e.void_reason = "voided", body.reason
    posting.void_source(db, actor.branch, "money_entry", e.id, f"{e.number} voided")
    db.commit()
    return entry_out(db, e)


# --- the two pages ---------------------------------------------------------------------------------------

def _row(**kw) -> dict:
    return {"missing_proof": kw.get("proof_url") is None, "detail": "", "link": None, "by": None, **kw}


def _gather(db: Session, actor: Actor, direction: Literal["in", "out"]) -> list[dict]:
    branch = actor.branch.id
    users = {u.id: u.full_name for u in db.scalars(select(User))}
    rows: list[dict] = []
    proof = lambda pid: f"/api/attachments/{pid}/file" if pid else None
    if direction == "in":
        names = {c.id: c.name for c in db.scalars(select(Customer))}
        for p in db.scalars(select(Payment).where(Payment.branch_id == branch)):
            inv = db.get(Invoice, p.invoice_id) if p.invoice_id else None
            rows.append(_row(id=p.id, number=p.number, date=p.received_at.date(), source="advance" if p.kind == "advance" else "invoice_payment",
                             party=names.get(p.customer_id, inv.walk_in_name if inv and inv.walk_in_name else "Walk-in customer"),
                             detail=inv.number if inv else "Advance on a quotation", account=p.account, reference=p.reference, amount=p.amount,
                             proof_url=proof(p.proof_id), no_proof_reason=p.no_proof_reason, status="posted" if p.status == "posted" else "voided",
                             link=f"/invoices/{p.invoice_id}" if p.invoice_id else f"/quotations/{p.quotation_id}", by=users.get(p.received_by)))
        entries = select(MoneyEntry).where(MoneyEntry.branch_id == branch, MoneyEntry.kind.in_(IN_KINDS + ("transfer",)))
    else:
        vendors = {v.id: v.name for v in db.scalars(select(Vendor))}
        for p in db.scalars(select(VendorPayment).where(VendorPayment.branch_id == branch)):
            rows.append(_row(id=p.id, number=p.number, date=p.paid_at.date(), source="vendor_payment", party=vendors.get(p.vendor_id, ""),
                             account=p.account, reference=p.reference, amount=p.amount, proof_url=proof(p.proof_id), no_proof_reason=p.no_proof_reason,
                             status="posted" if p.status == "posted" else "voided", link=f"/bills/{p.bill_id}", by=users.get(p.paid_by)))
        entries = select(MoneyEntry).where(MoneyEntry.branch_id == branch, MoneyEntry.kind.in_(("expense", "drawings", "transfer", "refund")))
    cats = {c.id: c.name for c in db.scalars(select(ExpenseCategory))}
    for e in db.scalars(entries):
        account = e.to_account if (direction == "in" and e.kind == "transfer") else e.account
        detail = cats.get(e.category_id) or (f"From {e.account} to {e.to_account}" if e.kind == "transfer" else "")
        link = None
        if e.kind == "refund":
            detail = "Advance given back" if e.payment_id else "Overpayment on an invoice"
            pay = db.get(Payment, e.payment_id) if e.payment_id else None
            link = f"/invoices/{e.invoice_id}" if e.invoice_id else f"/quotations/{pay.quotation_id}" if pay and pay.quotation_id else None
        rows.append(_row(id=e.id, number=e.number, date=e.occurred_on, source=e.kind, party=e.party, detail=detail, account=account,
                         reference=e.reference, amount=e.amount, proof_url=proof(e.proof_id), no_proof_reason=e.no_proof_reason,
                         status=e.status, entry_id=e.id, by=users.get(e.created_by), note=e.note, link=link))
    return rows


def page(db: Session, actor: Actor, direction: str, *, date_from, date_to, source, account, q, missing_proof, limit) -> dict:
    rows = _gather(db, actor, direction)  # type: ignore[arg-type]
    if date_from:
        rows = [r for r in rows if r["date"] >= date_from]
    if date_to:
        rows = [r for r in rows if r["date"] <= date_to]
    if source:
        rows = [r for r in rows if r["source"] == source]
    if account:
        rows = [r for r in rows if r["account"] == account]
    if missing_proof:
        rows = [r for r in rows if r["missing_proof"] and r["status"] == "posted"]
    if q.strip():
        needle = q.strip().lower()
        rows = [r for r in rows if needle in f"{r['party']} {r['number']} {r['reference']} {r['detail']}".lower()]
    rows.sort(key=lambda r: (r["date"], r["number"]), reverse=True)
    live = [r for r in rows if r["status"] == "posted"]
    by_account: dict[str, Decimal] = {}
    by_source: dict[str, Decimal] = {}
    for r in live:
        by_account[r["account"]] = by_account.get(r["account"], Decimal(0)) + r["amount"]
        by_source[r["source"]] = by_source.get(r["source"], Decimal(0)) + r["amount"]
    outside = sum((r["amount"] for r in live if r["source"] != "transfer"), Decimal(0))  # transfers just move money between accounts
    return {"rows": rows[:limit], "count": len(rows), "total": outside, "by_account": by_account, "by_source": by_source,
            "missing_proof": sum(1 for r in live if r["missing_proof"])}


@router.get("/money-in")
def money_in(date_from: date | None = None, date_to: date | None = None, source: Literal[IN_SOURCES] | None = None,  # type: ignore[valid-type]
             account: Literal["cash", "bank", "wallet"] | None = None, q: str = "", missing_proof: bool = False,
             limit: int = Query(300, ge=1, le=1000), actor: Actor = Depends(see_money), db: Session = Depends(get_db)):
    return page(db, actor, "in", date_from=date_from, date_to=date_to, source=source, account=account, q=q, missing_proof=missing_proof, limit=limit)


@router.get("/money-out")
def money_out(date_from: date | None = None, date_to: date | None = None, source: Literal[OUT_SOURCES] | None = None,  # type: ignore[valid-type]
              account: Literal["cash", "bank", "wallet"] | None = None, q: str = "", missing_proof: bool = False,
              limit: int = Query(300, ge=1, le=1000), actor: Actor = Depends(see_money), db: Session = Depends(get_db)):
    return page(db, actor, "out", date_from=date_from, date_to=date_to, source=source, account=account, q=q, missing_proof=missing_proof, limit=limit)
