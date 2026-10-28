"""Purchasing (spec R3): vendor -> purchase order -> goods received -> bill -> payment.

Prices change only through a goods receipt, which is also the only way a
purchase puts stock in and moves the weighted average cost. The vendor ledger
is derived from bills and payments, never typed.
"""

import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import Actor, current_actor, require
from app.db import get_db, utcnow
from app.models import (
    GoodsReceipt, GoodsReceiptLine, Item, ItemCode, PurchaseOrder, PurchaseOrderLine, User, Vendor, VendorBill, VendorPayment,
)
from app import posting
from app.numbering import next_number
from app.routers.estimates import Proof
from app.routers.workshop import _attach
from app.stock import StockError, move, on_hand_map
from app.validators import Email, Name, Phone, Text, normalize_code

router = APIRouter(prefix="/api", tags=["purchasing"])
can_vendors = require("vendors")
can_purchase = require("purchasing")
can_receive = require("goods-receipt")
can_pay = require("payments-out")

LOW_MARGIN_PCT = 10  # a receipt that leaves less margin than this is flagged (spec R6)
CENT = Decimal("0.01")


def can_see(actor: Actor = Depends(current_actor)) -> Actor:
    if not any(actor.can(p) for p in ("vendors", "purchasing", "goods-receipt", "payments-out")):
        raise HTTPException(403, "You don't have permission to do this")
    return actor


def money(v: Decimal) -> Decimal:
    return v.quantize(CENT, ROUND_HALF_UP)


def _get(db: Session, actor: Actor, model, id_: uuid.UUID, label: str, *, lock: bool = False):
    stmt = select(model).where(model.id == id_)
    obj = db.scalar(stmt.with_for_update() if lock else stmt)
    if not obj or obj.branch_id != actor.branch.id:
        raise HTTPException(404, f"{label} not found")
    return obj


# --- vendors ------------------------------------------------------------------------------------

class VendorIn(BaseModel):
    name: Name
    contact_person: Text = Field(default="", max_length=120)
    phone: Phone = ""
    email: Email = ""
    address: Text = Field(default="", max_length=300)
    terms_days: int = Field(default=0, ge=0, le=365)
    notes: Text = Field(default="", max_length=3000)


class VendorUpdate(VendorIn):
    is_active: bool = True
    version: int


def _owed(db: Session, vendor_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    """What each vendor is owed: posted bills less posted payments."""
    if not vendor_ids:
        return {}
    bills = dict(db.execute(select(VendorBill.vendor_id, func.sum(VendorBill.goods_value + VendorBill.adjustment))
                            .where(VendorBill.vendor_id.in_(vendor_ids), VendorBill.status == "posted")
                            .group_by(VendorBill.vendor_id)).all())
    paid = dict(db.execute(select(VendorPayment.vendor_id, func.sum(VendorPayment.amount))
                           .where(VendorPayment.vendor_id.in_(vendor_ids), VendorPayment.status == "posted")
                           .group_by(VendorPayment.vendor_id)).all())
    return {v: bills.get(v, Decimal(0)) - paid.get(v, Decimal(0)) for v in vendor_ids}


def vendor_out(v: Vendor, owed: Decimal | None = None) -> dict:
    data = {k: getattr(v, k) for k in ("id", "number", "name", "contact_person", "phone", "email", "address", "terms_days",
                                       "notes", "is_active", "version")}
    if owed is not None:
        data["owed"] = owed
    return data


@router.get("/vendors")
def list_vendors(q: str = "", include_inactive: bool = False, actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    stmt = select(Vendor).where(Vendor.branch_id == actor.branch.id).order_by(Vendor.name)
    if not include_inactive:
        stmt = stmt.where(Vendor.is_active)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Vendor.name.ilike(like), Vendor.phone.ilike(like), Vendor.number.ilike(like),
                              Vendor.contact_person.ilike(like)))
    vendors = db.scalars(stmt.limit(300)).all()
    owed = _owed(db, [v.id for v in vendors])
    return [vendor_out(v, owed[v.id]) for v in vendors]


@router.post("/vendors", status_code=201)
def create_vendor(body: VendorIn, actor: Actor = Depends(can_vendors), db: Session = Depends(get_db)):
    if db.scalar(select(Vendor.id).where(Vendor.branch_id == actor.branch.id, func.lower(Vendor.name) == body.name.lower())):
        raise HTTPException(409, "A vendor with this name already exists")
    v = Vendor(number=next_number(db, actor.branch, "vendor"), **body.model_dump())
    db.add(v)
    db.commit()
    return vendor_out(v, Decimal(0))


@router.put("/vendors/{vendor_id}")
def update_vendor(vendor_id: uuid.UUID, body: VendorUpdate, actor: Actor = Depends(can_vendors), db: Session = Depends(get_db)):
    v = _get(db, actor, Vendor, vendor_id, "Vendor")
    if body.version != v.version:
        raise HTTPException(409, "Someone else changed this vendor. Reload and try again.")
    clash = db.scalar(select(Vendor.id).where(Vendor.branch_id == actor.branch.id, func.lower(Vendor.name) == body.name.lower(),
                                              Vendor.id != v.id))
    if clash:
        raise HTTPException(409, "A vendor with this name already exists")
    for key, value in body.model_dump(exclude={"version"}).items():
        setattr(v, key, value)
    db.commit()
    return vendor_out(v, _owed(db, [v.id])[v.id])


@router.get("/vendors/{vendor_id}")
def get_vendor(vendor_id: uuid.UUID, actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    v = _get(db, actor, Vendor, vendor_id, "Vendor")
    bills = db.scalars(select(VendorBill).where(VendorBill.vendor_id == v.id)).all()
    payments = db.scalars(select(VendorPayment).where(VendorPayment.vendor_id == v.id)).all()
    # The ledger is built from bills and payments on every read; there is no stored balance to drift.
    entries = ([{"at": b.created_at, "kind": "bill", "id": b.id, "number": b.number, "void": b.status == "void",
                 "detail": b.vendor_invoice_no and f"Vendor invoice {b.vendor_invoice_no}", "amount": b.goods_value + b.adjustment}
                for b in bills] +
               [{"at": p.paid_at, "kind": "payment", "id": p.bill_id, "number": p.number, "void": p.status == "voided",
                 "detail": p.reference or p.account, "amount": -p.amount} for p in payments])
    entries.sort(key=lambda e: e["at"])
    running = Decimal(0)
    for e in entries:
        if not e["void"]:
            running += e["amount"]
        e["balance"] = running
    pos = db.scalars(select(PurchaseOrder).where(PurchaseOrder.vendor_id == v.id).order_by(PurchaseOrder.created_at.desc()).limit(20)).all()
    return {**vendor_out(v, running), "ledger": entries[::-1],
            "purchase_orders": [{"id": p.id, "number": p.number, "status": p.status, "created_at": p.created_at} for p in pos]}


# --- the picker ------------------------------------------------------------------------------------

@router.get("/purchase-catalog")
def purchase_catalog(q: str = Query(min_length=1, max_length=60), actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    """Stock items for a purchase order: by name, internal number, or a scanned barcode or part number."""
    like, norm = f"%{q.strip()}%", normalize_code(q)
    by_code = select(ItemCode.item_id).where(ItemCode.branch_id == actor.branch.id, ItemCode.code_norm == norm)
    items = db.scalars(select(Item).where(Item.branch_id == actor.branch.id, Item.is_active,
                                          or_(Item.id.in_(by_code), Item.name.ilike(like), Item.number.ilike(like), Item.brand.ilike(like)))
                       .order_by(Item.id.in_(by_code).desc(), Item.name).limit(10)).all()
    stock = on_hand_map(db, [i.id for i in items])
    return [{"id": i.id, "number": i.number, "name": i.name, "unit": i.unit, "avg_cost": i.avg_cost, "sale_price": i.sale_price,
             "on_hand": stock.get(i.id, Decimal(0)), "reorder_qty": i.reorder_qty,
             "codes": [c.code for c in i.codes]} for i in items]


# --- purchase orders ---------------------------------------------------------------------------------

def _received(db: Session, po: PurchaseOrder) -> dict[uuid.UUID, Decimal]:
    return dict(db.execute(select(GoodsReceiptLine.po_line_id, func.sum(GoodsReceiptLine.qty))
                           .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id)
                           .where(GoodsReceipt.purchase_order_id == po.id).group_by(GoodsReceiptLine.po_line_id)).all())


def _receipt_out(db: Session, g: GoodsReceipt) -> dict:
    bill = db.scalar(select(VendorBill).where(VendorBill.goods_receipt_id == g.id, VendorBill.status == "posted"))
    return {"id": g.id, "number": g.number, "received_on": g.received_on, "supplier_ref": g.supplier_ref, "notes": g.notes,
            "value": sum((money(l.qty * l.unit_cost) for l in g.lines), Decimal(0)),
            "lines": [{"id": l.id, "po_line_id": l.po_line_id, "item_id": l.item_id, "qty": l.qty, "unit_cost": l.unit_cost}
                      for l in g.lines],
            "bill": bill and {"id": bill.id, "number": bill.number}}


def po_out(db: Session, po: PurchaseOrder) -> dict:
    v = db.get(Vendor, po.vendor_id)
    items = {i.id: i for i in db.scalars(select(Item).where(Item.id.in_([l.item_id for l in po.lines])))}
    stock = on_hand_map(db, list(items))
    received = _received(db, po)
    lines = []
    for l in po.lines:
        i, got = items[l.item_id], received.get(l.id, Decimal(0))
        lines.append({"id": l.id, "item_id": l.item_id, "number": i.number, "name": i.name, "unit": i.unit, "qty": l.qty,
                      "unit_cost": l.unit_cost, "amount": money(l.qty * l.unit_cost), "received": got,
                      "outstanding": max(l.qty - got, Decimal(0)), "avg_cost": i.avg_cost, "sale_price": i.sale_price,
                      "on_hand": stock.get(i.id, Decimal(0)), "codes": [c.code for c in i.codes]})
    receipts = db.scalars(select(GoodsReceipt).where(GoodsReceipt.purchase_order_id == po.id).order_by(GoodsReceipt.created_at)).all()
    return {"id": po.id, "number": po.number, "status": po.status, "version": po.version, "expected_on": po.expected_on,
            "notes": po.notes, "sent_at": po.sent_at, "created_at": po.created_at, "closed_reason": po.closed_reason,
            "vendor": {"id": v.id, "number": v.number, "name": v.name, "phone": v.phone, "address": v.address,
                       "contact_person": v.contact_person, "terms_days": v.terms_days},
            "lines": lines, "total": sum((l["amount"] for l in lines), Decimal(0)),
            "receipts": [_receipt_out(db, g) for g in receipts]}


class PoLineIn(BaseModel):
    item_id: uuid.UUID
    qty: Decimal = Field(gt=0, le=100000, decimal_places=3)
    unit_cost: Decimal = Field(gt=0, le=100_000_000, decimal_places=4)


class PoIn(BaseModel):
    vendor_id: uuid.UUID
    lines: list[PoLineIn] = Field(min_length=1, max_length=200)
    expected_on: date | None = None
    notes: Text = Field(default="", max_length=3000)
    version: int | None = None  # sent when saving an existing draft


def _apply_po(db: Session, actor: Actor, po: PurchaseOrder, body: PoIn) -> None:
    vendor = _get(db, actor, Vendor, body.vendor_id, "Vendor")
    if not vendor.is_active:
        raise HTTPException(422, f"{vendor.name} is inactive. Reactivate the vendor first.")
    ids = [l.item_id for l in body.lines]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "An item is listed twice. Combine the quantities on one line.")
    items = {i.id: i for i in db.scalars(select(Item).where(Item.id.in_(ids), Item.branch_id == actor.branch.id))}
    for l in body.lines:
        item = items.get(l.item_id)
        if not item:
            raise HTTPException(422, "An item on this order wasn't found")
        if not item.is_active:
            raise HTTPException(422, f"{item.name} is inactive. Reactivate it or remove the line.")
    if body.expected_on and body.expected_on < date.today() and po.status == "draft" and po.id is None:
        raise HTTPException(422, "The expected date is in the past")
    po.vendor_id, po.expected_on, po.notes = body.vendor_id, body.expected_on, body.notes
    po.lines = [PurchaseOrderLine(position=n, **l.model_dump()) for n, l in enumerate(body.lines)]
    po.updated_at = utcnow()


@router.post("/purchase-orders", status_code=201)
def create_po(body: PoIn, actor: Actor = Depends(can_purchase), db: Session = Depends(get_db)):
    po = PurchaseOrder(number=next_number(db, actor.branch, "purchase_order"), vendor_id=body.vendor_id)
    _apply_po(db, actor, po, body)
    db.add(po)
    db.commit()
    return po_out(db, po)


@router.put("/purchase-orders/{po_id}")
def save_po(po_id: uuid.UUID, body: PoIn, actor: Actor = Depends(can_purchase), db: Session = Depends(get_db)):
    po = _get(db, actor, PurchaseOrder, po_id, "Purchase order", lock=True)
    if po.status != "draft":
        raise HTTPException(409, "Only a draft can be edited. Cancel this order and make a new one to change it.")
    if body.version is not None and body.version != po.version:
        raise HTTPException(409, "This order was changed on another device. Reload to continue.")
    _apply_po(db, actor, po, body)
    db.commit()
    return po_out(db, po)


@router.get("/purchase-orders")
def list_pos(status: Literal["open", "draft", "sent", "received", "closed", "all"] = "open", vendor_id: uuid.UUID | None = None,
             actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    stmt = (select(PurchaseOrder, Vendor).join(Vendor, Vendor.id == PurchaseOrder.vendor_id)
            .where(PurchaseOrder.branch_id == actor.branch.id).order_by(PurchaseOrder.created_at.desc()).limit(300))
    if vendor_id:
        stmt = stmt.where(PurchaseOrder.vendor_id == vendor_id)
    groups = {"open": ("draft", "sent", "partly_received"), "draft": ("draft",), "sent": ("sent", "partly_received"),
              "received": ("received",), "closed": ("closed", "cancelled")}
    if status != "all":
        stmt = stmt.where(PurchaseOrder.status.in_(groups[status]))
    out = []
    for po, v in db.execute(stmt):
        out.append({"id": po.id, "number": po.number, "status": po.status, "created_at": po.created_at, "expected_on": po.expected_on,
                    "vendor": {"id": v.id, "name": v.name}, "total": sum((money(l.qty * l.unit_cost) for l in po.lines), Decimal(0)),
                    "lines": len(po.lines)})
    return out


@router.get("/purchase-orders/{po_id}")
def get_po(po_id: uuid.UUID, actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    return po_out(db, _get(db, actor, PurchaseOrder, po_id, "Purchase order"))


class VersionIn(BaseModel):
    version: int


@router.post("/purchase-orders/{po_id}/send")
def send_po(po_id: uuid.UUID, body: VersionIn, actor: Actor = Depends(can_purchase), db: Session = Depends(get_db)):
    """Locks the order. (Sending it to the vendor on WhatsApp arrives with the messaging phase; print it for now.)"""
    po = _get(db, actor, PurchaseOrder, po_id, "Purchase order", lock=True)
    if po.status != "draft":
        raise HTTPException(409, "Already sent")
    if body.version != po.version:
        raise HTTPException(409, "This order was changed on another device. Reload to continue.")
    po.status, po.sent_at = "sent", utcnow()
    db.commit()
    return po_out(db, po)


class ReasonIn(BaseModel):
    reason: Text = Field(min_length=3, max_length=500)


@router.post("/purchase-orders/{po_id}/cancel")
def cancel_po(po_id: uuid.UUID, body: ReasonIn, actor: Actor = Depends(can_purchase), db: Session = Depends(get_db)):
    po = _get(db, actor, PurchaseOrder, po_id, "Purchase order", lock=True)
    if po.status not in ("draft", "sent"):
        raise HTTPException(409, "Only a draft or sent order can be cancelled. Close a part-received order instead.")
    po.status, po.closed_reason = "cancelled", body.reason
    db.commit()
    return po_out(db, po)


@router.post("/purchase-orders/{po_id}/close")
def close_po(po_id: uuid.UUID, body: ReasonIn, actor: Actor = Depends(can_purchase), db: Session = Depends(get_db)):
    """The vendor won't deliver the rest: what was received stands, the order stops waiting."""
    po = _get(db, actor, PurchaseOrder, po_id, "Purchase order", lock=True)
    if po.status != "partly_received":
        raise HTTPException(409, "Only a part-received order is closed early")
    po.status, po.closed_reason = "closed", body.reason
    db.commit()
    return po_out(db, po)


# --- goods received ----------------------------------------------------------------------------------

class ReceiptLineIn(BaseModel):
    po_line_id: uuid.UUID
    qty: Decimal = Field(ge=0, le=100000, decimal_places=3)
    unit_cost: Decimal = Field(gt=0, le=100_000_000, decimal_places=4)  # what it really cost, which may not be the PO's price
    sale_price: Decimal | None = Field(default=None, ge=0, le=100_000_000, decimal_places=2)  # optional new sale price


class ReceiptIn(BaseModel):
    lines: list[ReceiptLineIn] = Field(min_length=1, max_length=200)
    received_on: date | None = None
    supplier_ref: Text = Field(default="", max_length=60)
    notes: Text = Field(default="", max_length=1000)


@router.post("/purchase-orders/{po_id}/receive", status_code=201)
def receive(po_id: uuid.UUID, body: ReceiptIn, actor: Actor = Depends(can_receive), db: Session = Depends(get_db)):
    """Counts stock in. Each line puts its quantity into stock and moves the item's
    weighted average cost; partial deliveries are normal."""
    po = _get(db, actor, PurchaseOrder, po_id, "Purchase order", lock=True)
    if po.status not in ("sent", "partly_received"):
        raise HTTPException(409, {"draft": "Send the order before receiving against it", "received": "This order is fully received",
                                  "closed": "This order was closed", "cancelled": "This order was cancelled"}[po.status])
    if body.received_on and body.received_on > date.today():
        raise HTTPException(422, "The receipt date is in the future")
    got = _received(db, po)
    po_lines = {l.id: l for l in po.lines}
    taken = [l for l in body.lines if l.qty > 0]
    if not taken:
        raise HTTPException(422, "Enter the quantity that arrived on at least one line")
    if len({l.po_line_id for l in taken}) != len(taken):
        raise HTTPException(422, "A line is listed twice")
    for l in taken:
        pl = po_lines.get(l.po_line_id)
        if not pl:
            raise HTTPException(422, "A line isn't on this order")
        outstanding = pl.qty - got.get(pl.id, Decimal(0))
        if l.qty > outstanding:
            item = db.get(Item, pl.item_id)
            raise HTTPException(422, f"{item.name}: {l.qty.normalize():f} is more than the {outstanding.normalize():f} still expected")

    g = GoodsReceipt(number=next_number(db, actor.branch, "goods_receipt"), purchase_order_id=po.id, vendor_id=po.vendor_id,
                     received_on=body.received_on or date.today(), supplier_ref=body.supplier_ref, notes=body.notes)
    db.add(g)
    db.flush()
    warnings = []
    for n, l in enumerate(sorted(taken, key=lambda x: po_lines[x.po_line_id].item_id)):  # one lock order, so receipts can't deadlock
        pl = po_lines[l.po_line_id]
        item = db.get(Item, pl.item_id)
        line = GoodsReceiptLine(goods_receipt_id=g.id, position=n, po_line_id=pl.id, item_id=item.id, qty=l.qty, unit_cost=l.unit_cost)
        g.lines.append(line)
        db.flush()
        try:
            move(db, item.id, "grn", l.qty, unit_cost=l.unit_cost, reason=f"{g.number} from {po.number}",
                 source_type="goods_receipt_line", source_id=line.id)
        except StockError as e:
            raise HTTPException(409, str(e))
        # `item` is the row move() just locked and updated, so avg_cost is current without a refresh
        # (a refresh would throw the unflushed new average away).
        if l.sale_price is not None:
            item.sale_price = l.sale_price
        if item.sale_price > 0:
            margin = float((item.sale_price - item.avg_cost) / item.sale_price * 100)
            if margin < 0:
                warnings.append(f"{item.name}: the average cost {item.avg_cost:,.2f} is above the sale price {item.sale_price:,.2f}")
            elif margin < LOW_MARGIN_PCT:
                warnings.append(f"{item.name}: margin is only {margin:.0f}% at the new average cost")
        else:
            warnings.append(f"{item.name}: no sale price is set")
    db.flush()
    got = _received(db, po)
    po.status = "received" if all(got.get(l.id, Decimal(0)) >= l.qty for l in po.lines) else "partly_received"
    db.commit()
    return {**po_out(db, po), "new_receipt_id": g.id, "warnings": warnings}


# --- bills ---------------------------------------------------------------------------------------------

def bill_totals(db: Session, b: VendorBill) -> dict:
    paid = db.scalar(select(func.coalesce(func.sum(VendorPayment.amount), 0))
                     .where(VendorPayment.bill_id == b.id, VendorPayment.status == "posted"))
    total = b.goods_value + b.adjustment
    return {"goods_value": b.goods_value, "adjustment": b.adjustment, "total": total, "paid": paid, "balance": total - paid}


def pay_state(b: VendorBill, t: dict) -> str:
    return "void" if b.status == "void" else "paid" if t["balance"] <= 0 else "partly_paid" if t["paid"] > 0 else "unpaid"


def payment_out(db: Session, p: VendorPayment) -> dict:
    by = db.get(User, p.paid_by) if p.paid_by else None
    return {"id": p.id, "number": p.number, "status": p.status, "account": p.account, "reference": p.reference, "amount": p.amount,
            "paid_at": p.paid_at, "paid_by": by.full_name if by else None, "note": p.note, "void_reason": p.void_reason,
            "proof_url": f"/api/attachments/{p.proof_id}/file" if p.proof_id else None, "no_proof_reason": p.no_proof_reason}


def bill_out(db: Session, b: VendorBill) -> dict:
    v, g = db.get(Vendor, b.vendor_id), db.get(GoodsReceipt, b.goods_receipt_id)
    po = db.get(PurchaseOrder, g.purchase_order_id)
    items = {i.id: i for i in db.scalars(select(Item).where(Item.id.in_([l.item_id for l in g.lines])))}
    t = bill_totals(db, b)
    payments = db.scalars(select(VendorPayment).where(VendorPayment.bill_id == b.id).order_by(VendorPayment.paid_at)).all()
    return {"id": b.id, "number": b.number, "status": b.status, "pay_state": pay_state(b, t), "version": b.version,
            "vendor_invoice_no": b.vendor_invoice_no, "bill_date": b.bill_date, "due_on": b.due_on,
            "overdue": b.status == "posted" and t["balance"] > 0 and b.due_on < date.today(),
            "adjustment_reason": b.adjustment_reason, "void_reason": b.void_reason, "created_at": b.created_at, **t,
            "vendor": {"id": v.id, "name": v.name},
            "receipt": {"id": g.id, "number": g.number, "received_on": g.received_on, "supplier_ref": g.supplier_ref},
            "purchase_order": {"id": po.id, "number": po.number},
            "lines": [{"name": items[l.item_id].name, "number": items[l.item_id].number, "qty": l.qty, "unit_cost": l.unit_cost,
                       "amount": money(l.qty * l.unit_cost)} for l in g.lines],
            "payments": [payment_out(db, p) for p in payments]}


class BillIn(BaseModel):
    vendor_invoice_no: Text = Field(default="", max_length=60)
    bill_date: date
    due_on: date | None = None
    adjustment: Decimal = Field(default=Decimal(0), ge=-100_000_000, le=100_000_000, decimal_places=2)  # freight (+) or discount (-)
    adjustment_reason: Text = Field(default="", max_length=200)


@router.post("/goods-receipts/{grn_id}/bill", status_code=201)
def record_bill(grn_id: uuid.UUID, body: BillIn, actor: Actor = Depends(can_purchase), db: Session = Depends(get_db)):
    """What we owe for this delivery, as the vendor's invoice states it. The goods
    value comes from the receipt; freight or a discount goes in the adjustment."""
    g = _get(db, actor, GoodsReceipt, grn_id, "Goods receipt", lock=True)
    if db.scalar(select(VendorBill.id).where(VendorBill.goods_receipt_id == g.id, VendorBill.status == "posted")):
        raise HTTPException(409, "This receipt already has a bill")
    if body.bill_date > date.today():
        raise HTTPException(422, "The bill date is in the future")
    if body.adjustment != 0 and len(body.adjustment_reason) < 3:
        raise HTTPException(422, "Say what the adjustment is for (freight, discount)")
    value = sum((money(l.qty * l.unit_cost) for l in g.lines), Decimal(0))
    if value + body.adjustment <= 0:
        raise HTTPException(422, "The bill total must be more than zero")
    vendor = db.get(Vendor, g.vendor_id)
    if body.vendor_invoice_no:
        dup = db.scalar(select(VendorBill).where(VendorBill.vendor_id == vendor.id, VendorBill.status == "posted",
                                                 func.lower(VendorBill.vendor_invoice_no) == body.vendor_invoice_no.lower()))
        if dup:
            raise HTTPException(409, f"Invoice {body.vendor_invoice_no} from {vendor.name} is already recorded as {dup.number}")
    due = body.due_on or body.bill_date + timedelta(days=vendor.terms_days)
    if due < body.bill_date:
        raise HTTPException(422, "The due date is before the bill date")
    b = VendorBill(number=next_number(db, actor.branch, "vendor_bill"), vendor_id=vendor.id, goods_receipt_id=g.id,
                   vendor_invoice_no=body.vendor_invoice_no, bill_date=body.bill_date, due_on=due, goods_value=value,
                   adjustment=body.adjustment, adjustment_reason=body.adjustment_reason if body.adjustment else "")
    db.add(b)
    db.flush()
    posting.vendor_bill(db, actor.branch, b)
    db.commit()
    return bill_out(db, b)


@router.get("/bills")
def list_bills(status: Literal["owing", "paid", "overdue", "all"] = "owing", vendor_id: uuid.UUID | None = None,
               actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    stmt = (select(VendorBill, Vendor).join(Vendor, Vendor.id == VendorBill.vendor_id)
            .where(VendorBill.branch_id == actor.branch.id, VendorBill.status == "posted")
            .order_by(VendorBill.due_on, VendorBill.created_at).limit(500))
    if vendor_id:
        stmt = stmt.where(VendorBill.vendor_id == vendor_id)
    out = []
    for b, v in db.execute(stmt):
        t = bill_totals(db, b)
        state = pay_state(b, t)
        overdue = t["balance"] > 0 and b.due_on < date.today()
        if status == "owing" and state == "paid" or status == "paid" and state != "paid" or status == "overdue" and not overdue:
            continue
        out.append({"id": b.id, "number": b.number, "vendor": {"id": v.id, "name": v.name}, "vendor_invoice_no": b.vendor_invoice_no,
                    "bill_date": b.bill_date, "due_on": b.due_on, "total": t["total"], "balance": t["balance"], "pay_state": state,
                    "overdue": overdue})
    return out


@router.get("/bills/{bill_id}")
def get_bill(bill_id: uuid.UUID, actor: Actor = Depends(can_see), db: Session = Depends(get_db)):
    return bill_out(db, _get(db, actor, VendorBill, bill_id, "Bill"))


class VendorPaymentIn(Proof):
    amount: Decimal = Field(gt=0, le=100_000_000, decimal_places=2)
    account: Literal["cash", "bank", "wallet"]
    reference: Text = Field(default="", max_length=60)
    note: Text = Field(default="", max_length=500)


@router.post("/bills/{bill_id}/payments", status_code=201)
def pay_bill(bill_id: uuid.UUID, body: VendorPaymentIn, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    b = _get(db, actor, VendorBill, bill_id, "Bill", lock=True)
    if b.status != "posted":
        raise HTTPException(409, "This bill was voided")
    balance = bill_totals(db, b)["balance"]
    if body.amount > balance:
        raise HTTPException(422, f"That is more than the {balance:,.2f} still owed on this bill")
    if body.account != "cash" and not body.reference and not body.proof_id:
        raise HTTPException(422, "Add the transaction reference or a screenshot for a bank or wallet payment")
    p = VendorPayment(number=next_number(db, actor.branch, "vendor_payment"), vendor_id=b.vendor_id, bill_id=b.id,
                      paid_by=actor.user.id, **body.model_dump())
    db.add(p)
    db.flush()
    if body.proof_id:
        _attach(db, actor, [body.proof_id], "vendor_payments", p.id)
    posting.vendor_payment(db, actor.branch, p)
    db.commit()
    return bill_out(db, b)


@router.post("/vendor-payments/{payment_id}/void")
def void_payment(payment_id: uuid.UUID, body: ReasonIn, actor: Actor = Depends(can_pay), db: Session = Depends(get_db)):
    """A wrong payment stays on record, struck through; the bill owes that money again."""
    p = _get(db, actor, VendorPayment, payment_id, "Payment", lock=True)
    if p.status != "posted":
        raise HTTPException(409, "Already voided")
    p.status, p.void_reason = "voided", body.reason
    posting.void_source(db, actor.branch, "vendor_payment", p.id, f"Vendor payment {p.number} voided")
    db.commit()
    return bill_out(db, db.get(VendorBill, p.bill_id))


@router.post("/bills/{bill_id}/void")
def void_bill(bill_id: uuid.UUID, body: ReasonIn, actor: Actor = Depends(can_purchase), db: Session = Depends(get_db)):
    """Only before anything is paid. The goods stay in stock; the receipt can be billed again."""
    b = _get(db, actor, VendorBill, bill_id, "Bill", lock=True)
    if b.status != "posted":
        raise HTTPException(409, "Already voided")
    if bill_totals(db, b)["paid"] > 0:
        raise HTTPException(409, "Payments have been made on this bill. Void them first (with a reason).")
    b.status, b.void_reason = "void", body.reason
    posting.void_source(db, actor.branch, "vendor_bill", b.id, f"Bill {b.number} voided")
    db.commit()
    return bill_out(db, b)
