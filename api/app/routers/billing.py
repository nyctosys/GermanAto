"""Invoices (workshop and counter sale), payments, the gate pass and the
visit dossier (spec §2, §2.1)."""

import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import Actor, require
from app.db import get_db, utcnow
from app.models import (
    AuditLog, Car, Customer, Inspection, Invoice, InvoiceLine, JobCard, Payment, Quotation, RepairOrder, User, Visit,
)
from app import posting
from app.numbering import next_number
from app.routers.estimates import (
    LineIn, Proof, _line_refs, _targets, job_card_out, money, payment_out, quotation_out, totals,
)
from app.routers.repairs import _get_ro, _log, repair_order_out
from app.routers.workshop import _attach, _get_visit, _require_open, get_visit, person
from app.stock import StockError, move
from app.validators import Phone, Text

router = APIRouter(prefix="/api", tags=["billing"])
can_bill = require("invoices")
can_issue = require("invoice-issue")
can_take = require("payments-in")
can_visit = require("visits")


def _get_invoice(db: Session, actor: Actor, invoice_id: uuid.UUID, *, lock: bool = False) -> Invoice:
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    inv = db.scalar(stmt.with_for_update() if lock else stmt)
    if not inv or inv.branch_id != actor.branch.id:
        raise HTTPException(404, "Invoice not found")
    return inv


def _payments(db: Session, inv: Invoice) -> list[Payment]:
    return list(db.scalars(select(Payment).where(Payment.invoice_id == inv.id).order_by(Payment.received_at)))


def _held_advances(db: Session, visit_id: uuid.UUID) -> list[Payment]:
    """Advances on the visit not yet applied to an invoice: the customer's money we hold."""
    return list(db.scalars(select(Payment).where(Payment.visit_id == visit_id, Payment.kind == "advance",
                                                 Payment.status == "posted", Payment.invoice_id.is_(None))))


def balance_of(db: Session, inv: Invoice) -> dict:
    t = totals(inv)
    paid = sum((p.amount for p in _payments(db, inv) if p.status == "posted"), Decimal(0))
    return {**t, "paid": paid, "balance": t["total"] - paid}


def pay_status(inv: Invoice, b: dict) -> str:
    if inv.status != "issued":
        return inv.status
    return "paid" if b["balance"] <= 0 else "partly_paid" if b["paid"] > 0 else "unpaid"


def invoice_out(db: Session, inv: Invoice) -> dict:
    b = balance_of(db, inv)
    lines = _line_refs(db, inv.lines)
    for out, l in zip(lines, inv.lines):
        out.update(description=l.description, unit_price=l.unit_price, amount=money(l.qty * l.unit_price), in_quote=l.in_quote,
                   repair_order_line_id=l.repair_order_line_id)
    v = db.get(Visit, inv.visit_id) if inv.visit_id else None
    car = db.get(Car, inv.car_id) if inv.car_id else None
    customer = db.get(Customer, inv.customer_id) if inv.customer_id else None
    issuer = db.get(User, inv.issued_by) if inv.issued_by else None
    held = sum((p.amount for p in _held_advances(db, v.id)), Decimal(0)) if v and inv.status == "draft" else Decimal(0)
    credit = v and v.credit_released_by and db.get(User, v.credit_released_by)
    return {
        "id": inv.id, "number": inv.number, "kind": inv.kind, "status": inv.status, "pay_status": pay_status(inv, b),
        "version": inv.version, "include_tax": inv.include_tax, "tax_rate": inv.tax_rate, "discount": inv.discount,
        "notes": inv.notes, "created_at": inv.created_at, "issued_at": inv.issued_at,
        "issued_by": issuer.full_name if issuer else None, "repair_order_id": inv.repair_order_id,
        "visit": v and {"id": v.id, "number": v.number, "status": v.status, "car_id": v.car_id, "customer_id": v.customer_id,
                        "buyer_id": v.buyer_id, "odometer_in": v.odometer_in},
        "customer": person(customer), "walk_in_name": inv.walk_in_name, "walk_in_phone": inv.walk_in_phone,
        "car": car and {"id": car.id, "plate": car.plate, "make": car.make, "model": car.model, "year": car.year, "vin": car.vin},
        "lines": lines, "totals": {**b, "advance_held": held},
        "payments": [payment_out(db, p) for p in _payments(db, inv)],
        "credit_release": credit and {"by": credit.full_name, "reason": v.credit_reason},
    }


# --- workshop invoice ------------------------------------------------------------------------

def _lines_from_ro(ro: RepairOrder, prices: dict[uuid.UUID, Decimal] | None = None) -> list[InvoiceLine]:
    """What the repair order actually did: labour marked done, and parts at the
    quantity issued (spec §2.1 stock rules: the invoice bills what was issued)."""
    out = []
    for l in ro.lines:
        qty = l.issued_qty if l.kind == "part" else l.qty
        if l.state != "done" or qty <= 0:
            continue
        out.append(InvoiceLine(position=len(out), kind=l.kind, labour_code_id=l.labour_code_id, item_id=l.item_id,
                               repair_order_line_id=l.id, description=l.description, qty=qty, in_quote=l.in_quote,
                               unit_price=(prices or {}).get(l.id, l.unit_price)))
    return out


def _check_matches_ro(db: Session, inv: Invoice) -> None:
    ro = db.get(RepairOrder, inv.repair_order_id)
    want = {(l.repair_order_line_id, l.qty) for l in _lines_from_ro(ro)}
    if want != {(l.repair_order_line_id, l.qty) for l in inv.lines}:
        raise HTTPException(409, "The repair order changed after this invoice was drafted. Refresh the invoice from it first.")


@router.post("/repair-orders/{ro_id}/invoice", status_code=201)
def start_invoice(ro_id: uuid.UUID, actor: Actor = Depends(can_bill), db: Session = Depends(get_db)):
    ro = _get_ro(db, actor, ro_id, lock=True)
    v = db.get(Visit, ro.visit_id)
    _require_open(v)
    existing = db.scalar(select(Invoice).where(Invoice.visit_id == v.id, Invoice.kind == "workshop", Invoice.status != "void"))
    if existing:
        raise HTTPException(409, {"message": f"This visit already has invoice {existing.number}", "invoice_id": str(existing.id)})
    if ro.status != "ready":
        raise HTTPException(409, "Move the repair order to Ready before invoicing")
    lines = _lines_from_ro(ro)
    if not lines:
        raise HTTPException(422, "Nothing on the repair order is marked done")
    q = db.get(Quotation, ro.quotation_id)
    inv = Invoice(number=next_number(db, actor.branch, "invoice"), kind="workshop", visit_id=v.id, repair_order_id=ro.id,
                  customer_id=v.buyer_id or v.customer_id, car_id=v.car_id, include_tax=q.include_tax, tax_rate=q.tax_rate,
                  discount=q.discount, lines=lines)
    db.add(inv)
    db.commit()
    return invoice_out(db, inv)


@router.post("/invoices/{invoice_id}/refresh")
def refresh_invoice(invoice_id: uuid.UUID, actor: Actor = Depends(can_bill), db: Session = Depends(get_db)):
    """Re-reads the repair order, keeping any prices already edited on the draft."""
    inv = _get_invoice(db, actor, invoice_id, lock=True)
    if inv.status != "draft" or inv.kind != "workshop":
        raise HTTPException(409, "Only a draft workshop invoice is refreshed from its repair order")
    prices = {l.repair_order_line_id: l.unit_price for l in inv.lines}
    inv.lines = _lines_from_ro(db.get(RepairOrder, inv.repair_order_id), prices)
    inv.updated_at = utcnow()
    db.commit()
    return invoice_out(db, inv)


# --- counter sale ------------------------------------------------------------------------------

class SaleLineIn(LineIn):
    unit_price: Decimal = Field(ge=0, le=100_000_000, decimal_places=2)


class CounterSaleIn(BaseModel):
    customer_id: uuid.UUID | None = None
    car_id: uuid.UUID | None = None
    walk_in_name: Text = Field(default="", max_length=120)
    walk_in_phone: Phone = ""
    lines: list[SaleLineIn] = Field(min_length=1, max_length=200)
    include_tax: bool = True
    discount: Decimal = Field(default=Decimal(0), ge=0, decimal_places=2)
    notes: Text = Field(default="", max_length=3000)
    version: int | None = None  # sent when saving an existing draft

    @model_validator(mode="after")
    def parts_only(self):
        if any(l.kind != "part" for l in self.lines):
            raise ValueError("A counter sale sells parts only; work on a car goes through a visit")
        return self


def _apply_sale(db: Session, actor: Actor, inv: Invoice, body: CounterSaleIn) -> None:
    if body.customer_id and not db.get(Customer, body.customer_id):
        raise HTTPException(404, "Customer not found")
    if body.car_id and not db.get(Car, body.car_id):
        raise HTTPException(404, "Car not found")
    _, items = _targets(db, actor, body.lines)
    inv.customer_id, inv.car_id = body.customer_id, body.car_id
    inv.walk_in_name, inv.walk_in_phone = ("", "") if body.customer_id else (body.walk_in_name, body.walk_in_phone)
    inv.include_tax, inv.discount, inv.notes = body.include_tax, body.discount, body.notes
    inv.lines = [InvoiceLine(position=n, description=items[l.item_id].name, **l.model_dump()) for n, l in enumerate(body.lines)]
    inv.updated_at = utcnow()
    db.flush()
    if inv.discount > totals(inv)["subtotal"]:
        raise HTTPException(422, "The discount is more than the sale")


@router.post("/counter-sales", status_code=201)
def start_counter_sale(body: CounterSaleIn, actor: Actor = Depends(can_bill), db: Session = Depends(get_db)):
    inv = Invoice(number=next_number(db, actor.branch, "counter_sale"), kind="counter_sale", tax_rate=actor.branch.tax_rate)
    db.add(inv)
    _apply_sale(db, actor, inv, body)
    db.commit()
    return invoice_out(db, inv)


# --- shared invoice actions ------------------------------------------------------------------------

@router.get("/invoices")
def list_invoices(kind: Literal["workshop", "counter_sale", "all"] = "all",
                  status: Literal["draft", "unpaid", "paid", "all"] = "all", q: str = "",
                  actor: Actor = Depends(can_bill), db: Session = Depends(get_db)):
    stmt = (select(Invoice, Customer).outerjoin(Customer, Customer.id == Invoice.customer_id)
            .where(Invoice.branch_id == actor.branch.id, Invoice.status != "void")
            .order_by(Invoice.created_at.desc()).limit(300))
    if kind != "all":
        stmt = stmt.where(Invoice.kind == kind)
    if status == "draft":
        stmt = stmt.where(Invoice.status == "draft")
    elif status != "all":
        stmt = stmt.where(Invoice.status == "issued")
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Invoice.number.ilike(like), Customer.name.ilike(like), Invoice.walk_in_name.ilike(like)))
    out = []
    for inv, c in db.execute(stmt):
        b = balance_of(db, inv)
        ps = pay_status(inv, b)
        if status == "unpaid" and ps == "paid" or status == "paid" and ps != "paid":
            continue
        out.append({"id": inv.id, "number": inv.number, "kind": inv.kind, "status": inv.status, "pay_status": ps,
                    "total": b["total"], "balance": b["balance"], "created_at": inv.created_at, "issued_at": inv.issued_at,
                    "customer": c.name if c else inv.walk_in_name or "Walk-in"})
    return out


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: uuid.UUID, actor: Actor = Depends(can_bill), db: Session = Depends(get_db)):
    return invoice_out(db, _get_invoice(db, actor, invoice_id))


class WorkshopInvoiceIn(BaseModel):
    prices: dict[uuid.UUID, Decimal] = Field(default_factory=dict)  # invoice line id -> price
    include_tax: bool
    discount: Decimal = Field(default=Decimal(0), ge=0, decimal_places=2)
    notes: Text = Field(default="", max_length=3000)
    version: int


def _get_draft(db: Session, actor: Actor, invoice_id: uuid.UUID, kind: str, version: int | None) -> Invoice:
    inv = _get_invoice(db, actor, invoice_id, lock=True)
    if inv.kind != kind:
        raise HTTPException(404, "Invoice not found")
    if inv.status != "draft":
        raise HTTPException(409, "An issued invoice is locked. Corrections are made with a credit note.")
    if version is not None and version != inv.version:
        raise HTTPException(409, "This invoice was changed on another device. Reload to continue.")
    return inv


@router.put("/counter-sales/{invoice_id}")
def save_counter_sale(invoice_id: uuid.UUID, body: CounterSaleIn, actor: Actor = Depends(can_bill), db: Session = Depends(get_db)):
    inv = _get_draft(db, actor, invoice_id, "counter_sale", body.version)
    _apply_sale(db, actor, inv, body)
    db.commit()
    return invoice_out(db, inv)


@router.put("/invoices/{invoice_id}")
def save_invoice(invoice_id: uuid.UUID, body: WorkshopInvoiceIn, actor: Actor = Depends(can_bill), db: Session = Depends(get_db)):
    """Final prices stay editable until the invoice is issued (spec §2). The
    lines themselves come from the repair order."""
    inv = _get_draft(db, actor, invoice_id, "workshop", body.version)
    for l in inv.lines:
        price = body.prices.get(l.id)
        if price is not None:
            if price < 0:
                raise HTTPException(422, "A price can't be negative")
            l.unit_price = price
    inv.include_tax, inv.discount, inv.notes = body.include_tax, body.discount, body.notes
    inv.updated_at = utcnow()
    db.flush()
    if inv.discount > totals(inv)["subtotal"]:
        raise HTTPException(422, "The discount is more than the invoice's lines")
    db.commit()
    return invoice_out(db, inv)


class PaymentIn(Proof):
    amount: Decimal = Field(gt=0, le=100_000_000, decimal_places=2)
    account: Literal["cash", "bank", "wallet"]
    reference: Text = Field(default="", max_length=60)
    note: Text = Field(default="", max_length=500)


def _record_payment(db: Session, actor: Actor, inv: Invoice, body: PaymentIn) -> Payment:
    if body.account != "cash" and not body.reference and not body.proof_id:
        raise HTTPException(422, "Add the transaction reference or a screenshot for a bank or wallet payment")
    p = Payment(number=next_number(db, actor.branch, "payment"), kind="invoice", customer_id=inv.customer_id,
                visit_id=inv.visit_id, invoice_id=inv.id, received_by=actor.user.id, **body.model_dump())
    db.add(p)
    db.flush()
    if body.proof_id:
        _attach(db, actor, [body.proof_id], "payments", p.id)
    posting.customer_payment(db, actor.branch, p)
    return p


class IssueIn(BaseModel):
    version: int
    payments: list[PaymentIn] = Field(default_factory=list, max_length=5)  # counter sales are paid on the spot


@router.post("/invoices/{invoice_id}/issue")
def issue_invoice(invoice_id: uuid.UUID, body: IssueIn, actor: Actor = Depends(can_issue), db: Session = Depends(get_db)):
    """Locks the prices. A workshop invoice takes the visit's advances; a counter
    sale takes its stock out and its payment in, all in one transaction (§2.1)."""
    inv = _get_invoice(db, actor, invoice_id, lock=True)
    if inv.status != "draft":
        raise HTTPException(409, "Already issued")
    if body.version != inv.version:
        raise HTTPException(409, "This invoice was changed on another device. Reload to continue.")
    unpriced = [l.description for l in inv.lines if l.unit_price <= 0]
    if unpriced:
        raise HTTPException(422, f"Enter a price for {', '.join(unpriced)}")
    total = totals(inv)["total"]

    if inv.kind == "workshop":
        _require_open(db.get(Visit, inv.visit_id))
        _check_matches_ro(db, inv)
        if body.payments:
            raise HTTPException(422, "Record payments on the issued invoice")
        held = _held_advances(db, inv.visit_id)
        if sum((p.amount for p in held), Decimal(0)) > total:
            raise HTTPException(409, "The advances are more than the invoice. The difference must be refunded (admin approval) first.")
        for p in held:
            p.invoice_id = inv.id
        applied = held
    else:
        applied = []
        if sum((p.amount for p in body.payments), Decimal(0)) != total:
            raise HTTPException(422, f"A counter sale is paid in full on the spot: the payments must add up to {total:,.2f}")
        for l in inv.lines:
            try:
                move(db, l.item_id, "sale", -l.qty, reason=f"{inv.number}: counter sale", source_type="invoice_line", source_id=l.id)
            except StockError as e:
                raise HTTPException(409, str(e))
    inv.status, inv.issued_at, inv.issued_by = "issued", utcnow(), actor.user.id
    db.flush()
    posting.invoice_issued(db, actor.branch, inv)
    if applied:
        posting.advances_applied(db, actor.branch, inv, applied)
    for p in body.payments:  # counter sales only; checked above
        _record_payment(db, actor, inv, p)
    db.commit()
    return invoice_out(db, inv)


@router.post("/invoices/{invoice_id}/payments", status_code=201)
def take_payment(invoice_id: uuid.UUID, body: PaymentIn, actor: Actor = Depends(can_take), db: Session = Depends(get_db)):
    inv = _get_invoice(db, actor, invoice_id, lock=True)
    if inv.status != "issued":
        raise HTTPException(409, "Issue the invoice before taking payment")
    balance = balance_of(db, inv)["balance"]
    if body.amount > balance:
        raise HTTPException(422, f"That is more than the balance of {balance:,.2f}")
    _record_payment(db, actor, inv, body)
    db.commit()
    return invoice_out(db, inv)


class VoidIn(BaseModel):
    reason: Text = Field(min_length=3, max_length=500)


@router.post("/invoices/{invoice_id}/void")
def void_draft(invoice_id: uuid.UUID, body: VoidIn, actor: Actor = Depends(can_bill), db: Session = Depends(get_db)):
    """Throws away a draft (it keeps its number, marked void). Issued invoices need a credit note."""
    inv = _get_invoice(db, actor, invoice_id, lock=True)
    if inv.status != "draft":
        raise HTTPException(409, "Only a draft can be voided. An issued invoice is corrected with a credit note.")
    inv.status, inv.notes = "void", f"Voided: {body.reason}\n{inv.notes}".strip()
    db.commit()
    return invoice_out(db, inv)


# --- gate pass ---------------------------------------------------------------------------------

class GatePassIn(BaseModel):
    odometer_out: int | None = Field(default=None, ge=0, le=2_000_000)
    handed_to: Text = Field(default="", max_length=120)
    note: Text = Field(default="", max_length=500)
    credit_reason: Text = Field(default="", max_length=500)


def gate_check(db: Session, v: Visit) -> dict:
    """What stands between the car and the gate. Shown before the gate pass, enforced by it."""
    ro = db.scalar(select(RepairOrder).where(RepairOrder.visit_id == v.id))
    inv = db.scalar(select(Invoice).where(Invoice.visit_id == v.id, Invoice.kind == "workshop", Invoice.status != "void"))
    blockers, balance = [], Decimal(0)
    if ro and ro.status != "ready":
        blockers.append(f"Repair order {ro.number} isn't Ready")
    if ro and not inv:
        blockers.append("No invoice yet")
    if inv and inv.status == "draft":
        blockers.append(f"Invoice {inv.number} is still a draft")
    if inv and inv.status == "issued":
        balance = balance_of(db, inv)["balance"]
    if not inv and _held_advances(db, v.id):
        blockers.append("An advance is held with no invoice to use it. Refund it (admin approval) first.")
    warnings = []
    if db.scalar(select(Inspection.id).where(Inspection.visit_id == v.id, Inspection.status == "draft")):
        warnings.append("An inspection is still an unsigned draft")
    return {"blockers": blockers, "warnings": warnings, "balance": balance, "invoice_id": inv and inv.id}


@router.get("/visits/{visit_id}/gate-check")
def get_gate_check(visit_id: uuid.UUID, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    return gate_check(db, _get_visit(db, actor, visit_id))


@router.post("/visits/{visit_id}/gate-pass")
def gate_pass(visit_id: uuid.UUID, body: GatePassIn, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    """The car leaves. Blocked while there is a balance, unless someone with
    release-on-credit approves with a reason (owner decision 3)."""
    v = _get_visit(db, actor, visit_id, lock=True)
    _require_open(v)
    check = gate_check(db, v)
    if check["blockers"]:
        raise HTTPException(409, " ".join(check["blockers"]))
    if check["balance"] > 0:
        if not actor.can("release-on-credit"):
            raise HTTPException(403, f"There is a balance of {check['balance']:,.2f}. An admin must release the car on credit.")
        if len(body.credit_reason) < 5:
            raise HTTPException(422, "Give the reason for releasing the car with a balance")
        v.credit_released_by, v.credit_reason = actor.user.id, body.credit_reason
    car = db.get(Car, v.car_id)
    if body.odometer_out is not None:
        if v.odometer_in is not None and body.odometer_out < v.odometer_in:
            raise HTTPException(422, f"The exit reading is less than at check-in ({v.odometer_in:,} km)")
        car.odometer_km = max(car.odometer_km or 0, body.odometer_out)
    ro = db.scalar(select(RepairOrder).where(RepairOrder.visit_id == v.id))
    if ro:
        _log(db, ro, "status", body.note, from_status=ro.status, to_status="delivered")
        ro.status = "delivered"
    v.status, v.closed_at, v.odometer_out, v.released_by = "closed", utcnow(), body.odometer_out, actor.user.id
    v.handed_to, v.close_note = body.handed_to, body.note
    db.commit()
    return get_visit(v.id, actor, db)


# --- visit dossier -----------------------------------------------------------------------------

@router.get("/visits/{visit_id}/dossier")
def dossier(visit_id: uuid.UUID, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    """Everything about one visit, entry to exit, for the printable record (spec §2, R1)."""
    v = _get_visit(db, actor, visit_id)
    jc = db.scalar(select(JobCard).where(JobCard.visit_id == v.id))
    quotes = db.scalars(select(Quotation).where(Quotation.visit_id == v.id).order_by(Quotation.revision)).all()
    ro = db.scalar(select(RepairOrder).where(RepairOrder.visit_id == v.id))
    invoices = db.scalars(select(Invoice).where(Invoice.visit_id == v.id).order_by(Invoice.created_at)).all()
    payments = db.scalars(select(Payment).where(Payment.visit_id == v.id).order_by(Payment.received_at)).all()
    ids = [v.id, *(x.id for x in (jc, ro) if x), *(q.id for q in quotes), *(i.id for i in invoices), *(p.id for p in payments),
           *db.scalars(select(Inspection.id).where(Inspection.visit_id == v.id))]
    audit = db.execute(select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.user_id)
                       .where(AuditLog.entity_id.in_(ids)).order_by(AuditLog.at)).all()
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_([v.released_by, v.credit_released_by])))}
    return {
        "visit": get_visit(v.id, actor, db),
        "gate_pass": v.status == "closed" and {"at": v.closed_at, "odometer_out": v.odometer_out, "handed_to": v.handed_to,
                                               "note": v.close_note, "by": names.get(v.released_by),
                                               "credit": v.credit_released_by and {"by": names.get(v.credit_released_by), "reason": v.credit_reason}},
        "job_card": jc and job_card_out(db, jc),
        "quotations": [quotation_out(db, q) for q in quotes],
        "repair_order": ro and repair_order_out(db, ro),
        "invoices": [invoice_out(db, i) for i in invoices],
        "payments": [payment_out(db, p) for p in payments],
        "audit": [{"at": a.at, "by": by, "action": a.action, "entity_type": a.entity_type, "fields": sorted(a.changes)}
                  for a, by in audit],
    }
