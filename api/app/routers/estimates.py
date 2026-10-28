"""Job card -> quotation -> advance (spec §2, §2.2). The repair order picks up
from an approved quotation in the next stage."""

import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import Actor, current_actor, require
from app.db import get_db, utcnow
from app.models import (
    Car, Customer, Item, ItemCode, JobCard, JobCardLine, LabourCode, Payment, Quotation, QuotationLine, RepairOrder, User, Visit,
)
from app.numbering import next_number
from app.routers.workshop import _attach, _get_visit, _require_open, snapshot_of
from app.stock import on_hand_map
from app.validators import Text, normalize_code

router = APIRouter(prefix="/api", tags=["estimates"])
can_job = require("job-cards")
can_quote = require("quotations")
can_take = require("payments-in")

CENT = Decimal("0.01")
QUOTE_VALID_DAYS = 7


def can_estimate(actor: Actor = Depends(current_actor)) -> Actor:
    if not (actor.can("job-cards") or actor.can("quotations")):
        raise HTTPException(403, "You don't have permission to do this")
    return actor


def money(v: Decimal) -> Decimal:
    return v.quantize(CENT, ROUND_HALF_UP)


# --- shared line handling ---------------------------------------------------------------

class LineIn(BaseModel):
    kind: Literal["labour", "part"]
    labour_code_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None
    qty: Decimal = Field(default=Decimal("1"), gt=0, le=10000, decimal_places=3)

    @model_validator(mode="after")
    def one_target(self):
        if (self.kind == "labour") != bool(self.labour_code_id) or (self.kind == "part") != bool(self.item_id):
            raise ValueError("A labour line needs a labour code; a part line needs a stock item")
        return self


def _targets(db: Session, actor: Actor, lines: list[LineIn]) -> tuple[dict, dict]:
    """Labour codes and items by id, checked to exist in this branch and be active."""
    codes = {c.id: c for c in db.scalars(select(LabourCode).where(
        LabourCode.id.in_([l.labour_code_id for l in lines if l.labour_code_id]), LabourCode.branch_id == actor.branch.id))}
    items = {i.id: i for i in db.scalars(select(Item).where(
        Item.id.in_([l.item_id for l in lines if l.item_id]), Item.branch_id == actor.branch.id))}
    for l in lines:
        target = codes.get(l.labour_code_id) if l.kind == "labour" else items.get(l.item_id)
        if not target:
            raise HTTPException(422, "A labour code or item on this list wasn't found")
        if not target.is_active:
            raise HTTPException(422, f"{target.name} is inactive. Reactivate it or pick another.")
    return codes, items


def _line_refs(db: Session, lines) -> list[dict]:
    codes = {c.id: c for c in db.scalars(select(LabourCode).where(LabourCode.id.in_([l.labour_code_id for l in lines if l.labour_code_id])))}
    items = {i.id: i for i in db.scalars(select(Item).where(Item.id.in_([l.item_id for l in lines if l.item_id])))}
    stock = on_hand_map(db, list(items))
    out = []
    for l in lines:
        ref = {"id": l.id, "kind": l.kind, "labour_code_id": l.labour_code_id, "item_id": l.item_id, "qty": l.qty}
        if l.labour_code_id:
            c = codes[l.labour_code_id]
            ref["labour_code"] = {"code": c.code, "name": c.name}
        else:
            i = items[l.item_id]
            have = stock.get(i.id, Decimal(0))
            ref["item"] = {"number": i.number, "name": i.name, "unit": i.unit, "sale_price": i.sale_price,
                           "on_hand": have, "short": max(l.qty - have, Decimal(0))}
        out.append(ref)
    return out


@router.get("/estimate-catalog")
def estimate_catalog(q: str = Query(min_length=1, max_length=60), actor: Actor = Depends(can_estimate),
                     db: Session = Depends(get_db)):
    """The picker for job cards and quotations: labour codes and stock items only,
    never free text (spec §2). A scanned barcode or part number matches exactly."""
    like, norm = f"%{q.strip()}%", normalize_code(q)
    codes = db.scalars(select(LabourCode).where(LabourCode.branch_id == actor.branch.id, LabourCode.is_active,
                                                or_(LabourCode.code.ilike(like), LabourCode.name.ilike(like)))
                       .order_by(LabourCode.code).limit(8)).all()
    by_code = select(ItemCode.item_id).where(ItemCode.branch_id == actor.branch.id, ItemCode.code_norm == norm)
    items = db.scalars(select(Item).where(Item.branch_id == actor.branch.id, Item.is_active,
                                          or_(Item.id.in_(by_code), Item.name.ilike(like), Item.number.ilike(like)))
                       .order_by(Item.id.in_(by_code).desc(), Item.name).limit(8)).all()
    stock = on_hand_map(db, [i.id for i in items])
    return ([{"kind": "labour", "id": c.id, "code": c.code, "name": c.name, "category": c.category} for c in codes] +
            [{"kind": "part", "id": i.id, "code": i.number, "name": i.name, "unit": i.unit, "sale_price": i.sale_price,
              "on_hand": stock.get(i.id, Decimal(0))} for i in items])


# --- job card ---------------------------------------------------------------------------------

def _get_job_card(db: Session, actor: Actor, job_card_id: uuid.UUID) -> JobCard:
    jc = db.get(JobCard, job_card_id)
    if not jc or jc.branch_id != actor.branch.id:
        raise HTTPException(404, "Job card not found")
    return jc


def _current_quote(db: Session, visit_id: uuid.UUID) -> Quotation | None:
    return db.scalar(select(Quotation).where(Quotation.visit_id == visit_id, Quotation.status != "revised"))


def job_card_out(db: Session, jc: JobCard) -> dict:
    v = db.get(Visit, jc.visit_id)
    q = _current_quote(db, v.id)
    lines = _line_refs(db, jc.lines)
    for out, l in zip(lines, jc.lines):
        out["note"] = l.note
    return {"id": jc.id, "number": jc.number, "notes": jc.notes, "version": jc.version, "updated_at": jc.updated_at,
            "visit": {"id": v.id, "number": v.number, "status": v.status, "car_id": v.car_id, "customer_id": v.customer_id,
                      "buyer_id": v.buyer_id, "complaint": v.complaint},
            "lines": lines, "quotation": q and {"id": q.id, "number": q.number, "revision": q.revision, "status": status_of(q)}}


@router.post("/visits/{visit_id}/job-card")
def open_job_card(visit_id: uuid.UUID, response: Response, actor: Actor = Depends(can_job), db: Session = Depends(get_db)):
    """Opens the visit's job card, creating it the first time."""
    v = _get_visit(db, actor, visit_id, lock=True)
    jc = db.scalar(select(JobCard).where(JobCard.visit_id == v.id))
    if not jc:
        _require_open(v)
        jc = JobCard(number=next_number(db, actor.branch, "job_card"), visit_id=v.id)
        db.add(jc)
        db.commit()
        response.status_code = 201
    return job_card_out(db, jc)


@router.get("/job-cards/{job_card_id}")
def get_job_card(job_card_id: uuid.UUID, actor: Actor = Depends(can_job), db: Session = Depends(get_db)):
    return job_card_out(db, _get_job_card(db, actor, job_card_id))


class JobLineIn(LineIn):
    note: Text = Field(default="", max_length=300)


class JobCardIn(BaseModel):
    lines: list[JobLineIn] = Field(max_length=200)
    notes: Text = Field(default="", max_length=3000)
    version: int


@router.put("/job-cards/{job_card_id}")
def save_job_card(job_card_id: uuid.UUID, body: JobCardIn, actor: Actor = Depends(can_job), db: Session = Depends(get_db)):
    jc = _get_job_card(db, actor, job_card_id)
    _require_open(db.get(Visit, jc.visit_id))
    if body.version != jc.version:
        raise HTTPException(409, "This job card was changed on another device. Reload to continue.")
    _targets(db, actor, body.lines)
    jc.notes = body.notes
    jc.lines = [JobCardLine(position=n, **l.model_dump()) for n, l in enumerate(body.lines)]
    jc.updated_at = utcnow()  # lines changing alone must still bump the version
    db.commit()
    return job_card_out(db, jc)


# --- quotation --------------------------------------------------------------------------------

def status_of(q: Quotation) -> str:
    """'Expired' is derived: a sent quote past its validity date."""
    return "expired" if q.status == "sent" and q.valid_until < date.today() else q.status


def totals(q: Quotation) -> dict:
    lines = [l for l in q.lines if not l.declined]
    labour = sum((money(l.qty * l.unit_price) for l in lines if l.kind == "labour"), Decimal(0))
    parts = sum((money(l.qty * l.unit_price) for l in lines if l.kind == "part"), Decimal(0))
    subtotal = labour + parts
    discount = min(q.discount, subtotal)
    tax = money((subtotal - discount) * q.tax_rate / 100) if q.include_tax else Decimal(0)
    return {"labour": labour, "parts": parts, "subtotal": subtotal, "discount": discount, "tax": tax,
            "total": subtotal - discount + tax}


def advances_on(db: Session, visit_id: uuid.UUID) -> list[Payment]:
    return list(db.scalars(select(Payment).where(Payment.visit_id == visit_id, Payment.kind == "advance")
                           .order_by(Payment.received_at)))


def payment_out(db: Session, p: Payment) -> dict:
    by = db.get(User, p.received_by) if p.received_by else None
    return {"id": p.id, "number": p.number, "kind": p.kind, "status": p.status, "account": p.account, "reference": p.reference,
            "amount": p.amount, "received_at": p.received_at, "received_by": by.full_name if by else None, "note": p.note,
            "proof_url": f"/api/attachments/{p.proof_id}/file" if p.proof_id else None, "no_proof_reason": p.no_proof_reason,
            "quotation_id": p.quotation_id}


def quotation_out(db: Session, q: Quotation) -> dict:
    v = db.get(Visit, q.visit_id)
    approver = db.get(User, q.approved_by) if q.approved_by else None
    lines = _line_refs(db, q.lines)
    for out, l in zip(lines, q.lines):
        out.update(description=l.description, unit_price=l.unit_price, amount=money(l.qty * l.unit_price), declined=l.declined)
    t = totals(q)
    advances = advances_on(db, v.id)
    advance = sum((p.amount for p in advances if p.status == "posted"), Decimal(0))
    history = db.scalars(select(Quotation).where(Quotation.number == q.number).order_by(Quotation.revision)).all()
    return {
        "id": q.id, "number": q.number, "revision": q.revision, "status": status_of(q), "version": q.version,
        "include_tax": q.include_tax, "tax_rate": q.tax_rate, "discount": q.discount, "valid_until": q.valid_until,
        "notes": q.notes, "sent_at": q.sent_at, "created_at": q.created_at, "job_card_id": q.job_card_id,
        "approval": q.approved_at and {
            "at": q.approved_at, "by": approver.full_name if approver else None, "method": q.approval_method,
            "note": q.approval_note, "no_proof_reason": q.no_proof_reason,
            "proof_url": f"/api/attachments/{q.approval_proof_id}/file" if q.approval_proof_id else None},
        "rejected_reason": q.rejected_reason,
        "visit": {"id": v.id, "number": v.number, "status": v.status, "car_id": v.car_id, "customer_id": v.customer_id,
                  "buyer_id": v.buyer_id},
        "lines": lines, "totals": {**t, "advance": advance, "balance": t["total"] - advance},
        "revisions": [{"id": h.id, "revision": h.revision, "status": status_of(h)} for h in history],
        "advances": [payment_out(db, p) for p in advances],
        "people": snapshot_of(db, v, db.get(Car, v.car_id)),
        "repair_order": (ro := db.scalar(select(RepairOrder).where(RepairOrder.quotation_id == q.id))) and {"id": ro.id, "number": ro.number},  # car, owner and buyer for the printed copy
    }


def _get_quote(db: Session, actor: Actor, quotation_id: uuid.UUID, *, lock: bool = False) -> Quotation:
    stmt = select(Quotation).where(Quotation.id == quotation_id)
    q = db.scalar(stmt.with_for_update() if lock else stmt)
    if not q or q.branch_id != actor.branch.id:
        raise HTTPException(404, "Quotation not found")
    return q


def _check_version(q: Quotation, version: int) -> None:
    if version != q.version:
        raise HTTPException(409, "This quotation was changed on another device. Reload to continue.")


@router.post("/job-cards/{job_card_id}/quotation", status_code=201)
def start_quotation(job_card_id: uuid.UUID, actor: Actor = Depends(can_quote), db: Session = Depends(get_db)):
    """Copies the job card forward. Parts start at the item's sale price; labour
    prices are entered by hand (owner decision 6)."""
    jc = _get_job_card(db, actor, job_card_id)
    v = _get_visit(db, actor, jc.visit_id, lock=True)
    _require_open(v)
    existing = _current_quote(db, v.id)
    if existing:
        raise HTTPException(409, {"message": f"This visit already has quotation {existing.number}. Revise it instead.",
                                  "quotation_id": str(existing.id)})
    if not jc.lines:
        raise HTTPException(422, "Add the work to the job card first")
    codes, items = _targets(db, actor, [LineIn(kind=l.kind, labour_code_id=l.labour_code_id, item_id=l.item_id, qty=l.qty)
                                        for l in jc.lines])
    q = Quotation(number=next_number(db, actor.branch, "quotation"), visit_id=v.id, job_card_id=jc.id,
                  tax_rate=actor.branch.tax_rate, valid_until=date.today() + timedelta(days=QUOTE_VALID_DAYS),
                  lines=[QuotationLine(position=n, kind=l.kind, labour_code_id=l.labour_code_id, item_id=l.item_id, qty=l.qty,
                                       description=(codes[l.labour_code_id] if l.labour_code_id else items[l.item_id]).name,
                                       unit_price=items[l.item_id].sale_price if l.item_id else Decimal(0))
                         for n, l in enumerate(jc.lines)])
    db.add(q)
    db.commit()
    return quotation_out(db, q)


@router.get("/quotations")
def list_quotations(status: Literal["draft", "sent", "approved", "rejected", "expired", "converted", "all"] = "all",
                    actor: Actor = Depends(can_quote), db: Session = Depends(get_db)):
    stmt = (select(Quotation, Visit, Customer).join(Visit, Visit.id == Quotation.visit_id)
            .join(Customer, Customer.id == Visit.customer_id)
            .where(Quotation.branch_id == actor.branch.id, Quotation.status != "revised")
            .order_by(Quotation.created_at.desc()).limit(300))
    if status in ("sent", "expired"):
        stmt = stmt.where(Quotation.status == "sent",
                          Quotation.valid_until < date.today() if status == "expired" else Quotation.valid_until >= date.today())
    elif status != "all":
        stmt = stmt.where(Quotation.status == status)
    return [{"id": q.id, "number": q.number, "revision": q.revision, "status": status_of(q), "total": totals(q)["total"],
             "created_at": q.created_at, "valid_until": q.valid_until,
             "visit": {"id": v.id, "number": v.number}, "customer": {"id": c.id, "name": c.name}}
            for q, v, c in db.execute(stmt)]


@router.get("/quotations/{quotation_id}")
def get_quotation(quotation_id: uuid.UUID, actor: Actor = Depends(can_quote), db: Session = Depends(get_db)):
    return quotation_out(db, _get_quote(db, actor, quotation_id))


class QuoteLineIn(LineIn):
    unit_price: Decimal = Field(ge=0, le=100_000_000, decimal_places=2)


class QuotationIn(BaseModel):
    lines: list[QuoteLineIn] = Field(min_length=1, max_length=200)
    include_tax: bool
    discount: Decimal = Field(default=Decimal(0), ge=0, decimal_places=2)
    valid_until: date
    notes: Text = Field(default="", max_length=3000)
    version: int


@router.put("/quotations/{quotation_id}")
def save_quotation(quotation_id: uuid.UUID, body: QuotationIn, actor: Actor = Depends(can_quote), db: Session = Depends(get_db)):
    q = _get_quote(db, actor, quotation_id)
    if q.status != "draft":
        raise HTTPException(409, "Only a draft can be edited. Revise this quotation to change it.")
    _check_version(q, body.version)
    codes, items = _targets(db, actor, body.lines)
    q.lines = [QuotationLine(position=n, description=(codes[l.labour_code_id] if l.labour_code_id else items[l.item_id]).name,
                             **l.model_dump()) for n, l in enumerate(body.lines)]
    q.include_tax, q.discount, q.valid_until, q.notes = body.include_tax, body.discount, body.valid_until, body.notes
    q.updated_at = utcnow()
    db.flush()
    if q.discount > totals(q)["subtotal"]:
        raise HTTPException(422, "The discount is more than the quotation's lines")
    db.commit()
    return quotation_out(db, q)


class VersionIn(BaseModel):
    version: int


@router.post("/quotations/{quotation_id}/send")
def send_quotation(quotation_id: uuid.UUID, body: VersionIn, actor: Actor = Depends(can_quote), db: Session = Depends(get_db)):
    """Locks the draft. (WhatsApp delivery arrives with the messaging phase.)"""
    q = _get_quote(db, actor, quotation_id, lock=True)
    if q.status != "draft":
        raise HTTPException(409, "Already sent")
    _check_version(q, body.version)
    unpriced = [l.description for l in q.lines if l.unit_price <= 0]
    if unpriced:
        raise HTTPException(422, f"Enter a price for {', '.join(unpriced)}")
    if q.valid_until < date.today():
        raise HTTPException(422, "The validity date has passed. Set a new one.")
    q.status, q.sent_at = "sent", utcnow()
    db.commit()
    return quotation_out(db, q)


class Proof(BaseModel):
    """Proof is always required; when there truly is none, say why (owner decision 4)."""
    proof_id: uuid.UUID | None = None
    no_proof_reason: Text = Field(default="", max_length=500)

    @model_validator(mode="after")
    def proof_or_reason(self):
        if not self.proof_id and len(self.no_proof_reason) < 5:
            raise ValueError("Attach proof, or explain why there is none")
        return self


class ApproveIn(Proof):
    method: Literal["in_person", "whatsapp", "phone"]
    note: Text = Field(default="", max_length=1000)
    declined_line_ids: list[uuid.UUID] = Field(default_factory=list)
    version: int


@router.post("/quotations/{quotation_id}/approve")
def approve_quotation(quotation_id: uuid.UUID, body: ApproveIn, actor: Actor = Depends(can_quote), db: Session = Depends(get_db)):
    q = _get_quote(db, actor, quotation_id, lock=True)
    _check_version(q, body.version)
    if status_of(q) != "sent":
        raise HTTPException(409, {"draft": "Send the quotation before recording approval",
                                  "expired": "This quotation has expired. Revise it to send a new version."}.get(
                                      status_of(q), f"This quotation is {status_of(q)}"))
    declined = set(body.declined_line_ids)
    if declined - {l.id for l in q.lines}:
        raise HTTPException(422, "A declined line isn't on this quotation")
    if declined >= {l.id for l in q.lines}:
        raise HTTPException(422, "Nothing is approved. Reject the quotation instead.")
    for l in q.lines:
        l.declined = l.id in declined
    if body.proof_id:
        _attach(db, actor, [body.proof_id], "quotations", q.id)
    q.status, q.approved_at, q.approved_by = "approved", utcnow(), actor.user.id
    q.approval_method, q.approval_note = body.method, body.note
    q.approval_proof_id, q.no_proof_reason = body.proof_id, body.no_proof_reason
    db.commit()
    return quotation_out(db, q)


class RejectIn(BaseModel):
    reason: Text = Field(min_length=3, max_length=500)
    version: int


@router.post("/quotations/{quotation_id}/reject")
def reject_quotation(quotation_id: uuid.UUID, body: RejectIn, actor: Actor = Depends(can_quote), db: Session = Depends(get_db)):
    q = _get_quote(db, actor, quotation_id, lock=True)
    _check_version(q, body.version)
    if q.status != "sent":
        raise HTTPException(409, "Only a sent quotation can be rejected")
    q.status, q.rejected_reason = "rejected", body.reason
    db.commit()
    return quotation_out(db, q)


@router.post("/quotations/{quotation_id}/revise", status_code=201)
def revise_quotation(quotation_id: uuid.UUID, actor: Actor = Depends(can_quote), db: Session = Depends(get_db)):
    """A new draft revision with the same lines and prices. The old one stays,
    approval and all, but no longer counts (§2.2)."""
    old = _get_quote(db, actor, quotation_id, lock=True)
    _require_open(db.get(Visit, old.visit_id))
    if old.status not in ("sent", "approved", "rejected"):
        raise HTTPException(409, "A draft is edited directly" if old.status == "draft" else f"This quotation is {old.status}")
    old.status = "revised"
    db.flush()  # free the one-current-quotation slot before the new revision takes it
    new = Quotation(number=old.number, revision=old.revision + 1, supersedes_id=old.id, visit_id=old.visit_id,
                    job_card_id=old.job_card_id, tax_rate=actor.branch.tax_rate, include_tax=old.include_tax,
                    discount=old.discount, notes=old.notes, valid_until=date.today() + timedelta(days=QUOTE_VALID_DAYS),
                    lines=[QuotationLine(position=l.position, kind=l.kind, labour_code_id=l.labour_code_id, item_id=l.item_id,
                                         description=l.description, qty=l.qty, unit_price=l.unit_price) for l in old.lines])
    db.add(new)
    db.commit()
    return quotation_out(db, new)


# --- advance ---------------------------------------------------------------------------------

class AdvanceIn(Proof):
    amount: Decimal = Field(gt=0, le=100_000_000, decimal_places=2)
    account: Literal["cash", "bank", "wallet"]
    reference: Text = Field(default="", max_length=60)
    note: Text = Field(default="", max_length=500)


@router.post("/quotations/{quotation_id}/advances", status_code=201)
def take_advance(quotation_id: uuid.UUID, body: AdvanceIn, actor: Actor = Depends(can_take), db: Session = Depends(get_db)):
    """Held as the customer's money until the invoice uses it (§2.2)."""
    q = _get_quote(db, actor, quotation_id, lock=True)
    v = db.get(Visit, q.visit_id)
    _require_open(v)
    if status_of(q) not in ("sent", "approved", "converted"):
        raise HTTPException(409, "An advance can be taken once the quotation is sent or approved")
    if body.account != "cash" and not body.reference and not body.proof_id:
        raise HTTPException(422, "Add the transaction reference or a screenshot for a bank or wallet payment")
    p = Payment(number=next_number(db, actor.branch, "payment"), kind="advance", customer_id=v.buyer_id or v.customer_id,
                visit_id=v.id, quotation_id=q.id, received_by=actor.user.id, **body.model_dump())
    db.add(p)
    db.flush()
    if body.proof_id:
        _attach(db, actor, [body.proof_id], "payments", p.id)
    db.commit()
    return payment_out(db, p)
