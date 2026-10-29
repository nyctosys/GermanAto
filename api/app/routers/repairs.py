"""Repair order: the work actually done, parts issued from stock, and the
activity trail (spec §2, §2.3)."""

import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import Actor, require
from app import messaging
from app.models import Car, Customer, Visit  # noqa: F811
from app.db import get_db
from app.models import (
    RO_STAGES, Attachment, Car, Customer, Invoice, Quotation, RepairOrder, RepairOrderActivity, RepairOrderLine, StockMovement, User,
    UserBranch, Visit,
)
from app.numbering import next_number
from app.routers.estimates import LineIn, Proof, _get_quote, _line_refs, _targets, money, status_of
from app.routers.workshop import _attach, _require_open, snapshot_of
from app.stock import StockError, move
from app.validators import Text

router = APIRouter(prefix="/api", tags=["repairs"])
can_repair = require("repair-orders")

STAGE_NAMES = {
    "received": "Received", "in_repair": "In repair", "testing": "Testing",
    "ready": "Ready", "delivered": "Delivered", "on_hold": "On hold",
}
WORKING = RO_STAGES[:-1]  # delivered is set by the gate pass


def _get_ro(db: Session, actor: Actor, ro_id: uuid.UUID, *, lock: bool = False) -> RepairOrder:
    stmt = select(RepairOrder).where(RepairOrder.id == ro_id)
    ro = db.scalar(stmt.with_for_update() if lock else stmt)
    if not ro or ro.branch_id != actor.branch.id:
        raise HTTPException(404, "Repair order not found")
    return ro


def _require_working(db: Session, ro: RepairOrder) -> None:
    _require_open(db.get(Visit, ro.visit_id))
    if ro.status == "delivered":
        raise HTTPException(409, "This car has been delivered; the repair order is closed")


def _work_stage(ro: RepairOrder) -> str:
    """The stage that gates work: on hold resumes to held_from."""
    return ro.held_from if ro.status == "on_hold" else ro.status


def _refuse_stage(ro: RepairOrder, action: str, allowed: set[str]) -> None:
    stage = _work_stage(ro)
    if stage not in allowed:
        names = ", ".join(STAGE_NAMES[s].lower() for s in RO_STAGES if s in allowed)
        raise HTTPException(409, f"You can only {action} while the job is {names}. It is {STAGE_NAMES[stage].lower()}.")


def _log(db: Session, ro: RepairOrder, kind: str, body: str = "", **extra) -> RepairOrderActivity:
    entry = RepairOrderActivity(repair_order_id=ro.id, kind=kind, body=body, **extra)
    db.add(entry)
    return entry


def _line(ro: RepairOrder, line_id: uuid.UUID) -> RepairOrderLine:
    line = next((l for l in ro.lines if l.id == line_id), None)
    if not line:
        raise HTTPException(404, "That line isn't on this repair order")
    return line


def repair_order_out(db: Session, ro: RepairOrder) -> dict:
    v = db.get(Visit, ro.visit_id)
    q = db.get(Quotation, ro.quotation_id)
    techs = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_([l.technician_id for l in ro.lines if l.technician_id])))}
    lines = _line_refs(db, ro.lines)
    for out, l in zip(lines, ro.lines):
        out.update(description=l.description, unit_price=l.unit_price, amount=money(l.qty * l.unit_price), in_quote=l.in_quote,
                   approval=None if l.in_quote else {"method": l.approval_method, "reason": l.approval_reason,
                                                    "proof_url": f"/api/attachments/{l.approval_proof_id}/file" if l.approval_proof_id else None},
                   state=l.state, technician_id=l.technician_id, technician=techs.get(l.technician_id), issued_qty=l.issued_qty)
    entries = db.execute(select(RepairOrderActivity, User.full_name).outerjoin(User, User.id == RepairOrderActivity.created_by)
                         .where(RepairOrderActivity.repair_order_id == ro.id).order_by(RepairOrderActivity.created_at.desc())).all()
    photos: dict = {}
    for a in db.scalars(select(Attachment).where(Attachment.entity_type == "ro_activity",
                                                 Attachment.entity_id.in_([e.id for e, _ in entries]))):
        photos.setdefault(a.entity_id, []).append({"id": a.id, "name": a.original_name, "url": f"/api/attachments/{a.id}/file"})
    return {
        "id": ro.id, "number": ro.number, "status": ro.status, "held_from": ro.held_from, "version": ro.version,
        "created_at": ro.created_at,
        "quotation": {"id": q.id, "number": q.number, "revision": q.revision},
        "visit": {"id": v.id, "number": v.number, "status": v.status, "car_id": v.car_id, "customer_id": v.customer_id,
                  "buyer_id": v.buyer_id, "complaint": v.complaint, "odometer_in": v.odometer_in,
                  "fuel_eighths": v.fuel_eighths, "condition_notes": v.condition_notes, "items_left": v.items_left},
        "people": snapshot_of(db, v, db.get(Car, v.car_id)),
        "invoice": (inv := db.scalar(select(Invoice).where(Invoice.repair_order_id == ro.id, Invoice.status != "void")))
                   and {"id": inv.id, "number": inv.number, "status": inv.status},
        "lines": lines,
        "activity": [{"id": e.id, "kind": e.kind, "body": e.body, "from_status": e.from_status, "to_status": e.to_status,
                      "line_id": e.line_id, "customer_visible": e.customer_visible, "at": e.created_at, "by": by,
                      "photos": photos.get(e.id, [])} for e, by in entries],
    }


@router.post("/quotations/{quotation_id}/repair-order", status_code=201)
def start_repair_order(quotation_id: uuid.UUID, actor: Actor = Depends(can_repair), db: Session = Depends(get_db)):
    """Carries the approved lines and agreed prices; declined lines stay behind."""
    q = _get_quote(db, actor, quotation_id, lock=True)
    v = db.get(Visit, q.visit_id)
    _require_open(v)
    existing = db.scalar(select(RepairOrder).where(RepairOrder.visit_id == v.id))
    if existing:
        raise HTTPException(409, {"message": f"This visit already has repair order {existing.number}",
                                  "repair_order_id": str(existing.id)})
    if status_of(q) != "approved":
        raise HTTPException(409, "A repair order is made from an approved quotation")
    ro = RepairOrder(number=next_number(db, actor.branch, "repair_order"), visit_id=v.id, quotation_id=q.id,
                     lines=[RepairOrderLine(position=n, kind=l.kind, labour_code_id=l.labour_code_id, item_id=l.item_id,
                                            description=l.description, qty=l.qty, unit_price=l.unit_price)
                            for n, l in enumerate(x for x in q.lines if not x.declined)])
    db.add(ro)
    db.flush()
    q.status = "converted"
    _log(db, ro, "status", f"Made from quotation {q.number}" + (f", revision {q.revision}" if q.revision > 1 else ""),
         to_status="received")
    db.commit()
    return repair_order_out(db, ro)


@router.get("/repair-orders")
def list_repair_orders(status: Literal["active", "ready", "on_hold", "delivered", "all"] = "active", q: str = "",
                       actor: Actor = Depends(can_repair), db: Session = Depends(get_db)):
    stmt = (select(RepairOrder, Visit, Customer).join(Visit, Visit.id == RepairOrder.visit_id)
            .join(Customer, Customer.id == Visit.customer_id).join(Car, Car.id == Visit.car_id)
            .where(RepairOrder.branch_id == actor.branch.id).order_by(RepairOrder.created_at.desc()).limit(300))
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(RepairOrder.number.ilike(like), Visit.number.ilike(like), Customer.name.ilike(like),
                              Customer.phone.ilike(like), Car.plate.ilike(like)))
    if status == "active":
        stmt = stmt.where(RepairOrder.status.not_in(("ready", "delivered")))
    elif status != "all":
        stmt = stmt.where(RepairOrder.status == status)
    out = []
    for ro, v, c in db.execute(stmt):
        car = db.get(Car, v.car_id)
        pending = sum(1 for l in ro.lines if l.state == "pending")
        out.append({"id": ro.id, "number": ro.number, "status": ro.status, "created_at": ro.created_at, "pending": pending,
                    "lines": len(ro.lines), "visit": {"id": v.id, "number": v.number}, "customer": {"id": c.id, "name": c.name},
                    "car": {"plate": car.plate, "make": car.make, "model": car.model, "year": car.year}})
    return out


@router.get("/repair-orders/{ro_id}")
def get_repair_order(ro_id: uuid.UUID, actor: Actor = Depends(can_repair), db: Session = Depends(get_db)):
    return repair_order_out(db, _get_ro(db, actor, ro_id))


@router.get("/technicians")
def technicians(actor: Actor = Depends(can_repair), db: Session = Depends(get_db)):
    """Active people at this branch, to assign work to."""
    rows = db.scalars(select(User).join(UserBranch, UserBranch.user_id == User.id)
                      .where(UserBranch.branch_id == actor.branch.id, User.is_active).order_by(User.full_name))
    return [{"id": u.id, "name": u.full_name} for u in rows]


# --- status ------------------------------------------------------------------------------------

class StatusIn(BaseModel):
    to: Literal["received", "in_repair", "testing", "ready", "on_hold"]
    note: Text = Field(default="", max_length=1000)
    customer_visible: bool = False
    version: int


@router.post("/repair-orders/{ro_id}/status")
def change_status(ro_id: uuid.UUID, body: StatusIn, actor: Actor = Depends(can_repair), db: Session = Depends(get_db)):
    ro = _get_ro(db, actor, ro_id, lock=True)
    _require_working(db, ro)
    if body.version != ro.version:
        raise HTTPException(409, "This repair order was changed on another device. Reload to continue.")
    if body.to == ro.status:
        raise HTTPException(422, f"It is already {STAGE_NAMES[ro.status].lower()}")
    current = ro.held_from if ro.status == "on_hold" else ro.status
    backwards = body.to != "on_hold" and WORKING.index(body.to) < WORKING.index(current)
    if (body.to == "on_hold" or backwards) and len(body.note) < 3:
        raise HTTPException(422, "Say why: a note is needed to put a job on hold or move it back a stage")
    if body.to == "ready" and current != "testing":
        raise HTTPException(422, "A car cannot go straight to Ready. Move it to Testing first, check the work, then Ready")
    # Leaving In repair for Testing, or Testing for Ready, needs every line Done or Not done.
    if body.to in ("testing", "ready") and not backwards:
        pending = [l.description for l in ro.lines if l.state == "pending"]
        if pending:
            raise HTTPException(422, f"Mark these done or not done first: {', '.join(pending)}")
    ro.held_from = current if body.to == "on_hold" else None
    _log(db, ro, "status", body.note, from_status=ro.status, to_status=body.to, customer_visible=body.customer_visible)
    ro.status = body.to
    if body.to == "ready":
        v = db.get(Visit, ro.visit_id)
        car = db.get(Car, v.car_id)
        messaging.queue(db, actor.branch, db.get(Customer, v.customer_id), "car_ready",
                        {"car": f"{car.make} {car.model}".strip()}, f"ready:{ro.id}:{ro.version}")
    db.commit()
    if body.to == "ready":
        messaging.flush(db, actor.branch.id)
    return repair_order_out(db, ro)


# --- lines -------------------------------------------------------------------------------------

class ExtraLineIn(LineIn, Proof):
    """Extra work needs the customer's go-ahead: how they agreed, with proof or a reason."""
    unit_price: Decimal = Field(gt=0, le=100_000_000, decimal_places=2)
    reason: Text = Field(min_length=3, max_length=500)
    approval_method: Literal["in_person", "whatsapp", "phone"]


@router.post("/repair-orders/{ro_id}/lines", status_code=201)
def add_line(ro_id: uuid.UUID, body: ExtraLineIn, actor: Actor = Depends(can_repair), db: Session = Depends(get_db)):
    """Extra work found during the repair. Flagged 'not in quote' so the
    invoice and the customer both see it was added after approval."""
    ro = _get_ro(db, actor, ro_id, lock=True)
    _require_working(db, ro)
    _refuse_stage(ro, "add extra work", {"in_repair", "testing"})
    codes, items = _targets(db, actor, [body])
    name = (codes[body.labour_code_id] if body.labour_code_id else items[body.item_id]).name
    line = RepairOrderLine(position=len(ro.lines), in_quote=False, description=name, approval_method=body.approval_method,
                           approval_proof_id=body.proof_id, approval_reason=body.no_proof_reason,
                           **body.model_dump(exclude={"reason", "approval_method", "proof_id", "no_proof_reason"}))
    ro.lines.append(line)
    db.flush()
    if body.proof_id:
        _attach(db, actor, [body.proof_id], "ro_line_approval", line.id)
    _log(db, ro, "line", f"Added {name} (not in the quotation): {body.reason}. Customer agreed {body.approval_method.replace('_', ' ')}.", line_id=line.id)
    db.commit()
    return repair_order_out(db, ro)


class LineUpdate(BaseModel):
    state: Literal["pending", "done", "not_done"] | None = None
    technician_id: uuid.UUID | None = None
    clear_technician: bool = False


@router.patch("/repair-orders/{ro_id}/lines/{line_id}")
def update_line(ro_id: uuid.UUID, line_id: uuid.UUID, body: LineUpdate, actor: Actor = Depends(can_repair),
                db: Session = Depends(get_db)):
    ro = _get_ro(db, actor, ro_id, lock=True)
    _require_working(db, ro)
    line = _line(ro, line_id)
    if body.technician_id or body.clear_technician:
        _refuse_stage(ro, "assign a technician", {"received", "in_repair", "testing"})
        tech = body.technician_id and db.scalar(select(User).join(UserBranch, UserBranch.user_id == User.id).where(
            User.id == body.technician_id, UserBranch.branch_id == actor.branch.id, User.is_active))
        if body.technician_id and not tech:
            raise HTTPException(422, "That person isn't active at this branch")
        line.technician_id = body.technician_id if not body.clear_technician else None
    if body.state and body.state != line.state:
        # In repair / testing only. Received is read-mostly; Ready+ is locked.
        _refuse_stage(ro, "mark work done or not done", {"in_repair", "testing"})
        if body.state == "done" and line.kind == "part" and line.issued_qty <= 0:
            raise HTTPException(422, f"Issue {line.description} from stock before marking it done")
        if body.state == "not_done" and line.issued_qty > 0:
            raise HTTPException(422, "Return the issued parts to stock before marking this not done")
        line.state = body.state
        _log(db, ro, "line", f"{line.description}: {body.state.replace('_', ' ')}", line_id=line.id)
    db.commit()
    return repair_order_out(db, ro)


@router.delete("/repair-orders/{ro_id}/lines/{line_id}")
def remove_line(ro_id: uuid.UUID, line_id: uuid.UUID, actor: Actor = Depends(can_repair), db: Session = Depends(get_db)):
    ro = _get_ro(db, actor, ro_id, lock=True)
    _require_working(db, ro)
    _refuse_stage(ro, "remove a line", {"in_repair", "testing"})
    line = _line(ro, line_id)
    if line.in_quote:
        raise HTTPException(409, "A line the customer approved stays on the order. Mark it not done instead.")
    if line.issued_qty > 0:
        raise HTTPException(409, "Return the issued parts to stock first")
    ro.lines.remove(line)
    _log(db, ro, "line", f"Removed {line.description}")
    db.commit()
    return repair_order_out(db, ro)


class QtyIn(BaseModel):
    qty: Decimal = Field(gt=0, le=10000, decimal_places=3)


@router.post("/repair-orders/{ro_id}/lines/{line_id}/issue")
def issue_part(ro_id: uuid.UUID, line_id: uuid.UUID, body: QtyIn, actor: Actor = Depends(can_repair),
               db: Session = Depends(get_db)):
    """Takes the part out of stock at average cost (spec D4).
    Main window is In repair; Received allows an early issue; Testing allows a top-up."""
    ro = _get_ro(db, actor, ro_id, lock=True)
    _require_working(db, ro)
    _refuse_stage(ro, "issue parts from stock", {"received", "in_repair", "testing"})
    line = _line(ro, line_id)
    if line.kind != "part":
        raise HTTPException(422, "Only parts are issued from stock")
    remaining = line.qty - line.issued_qty
    if body.qty > remaining:
        raise HTTPException(422, f"Only {remaining.normalize():f} still to issue on this line")
    try:
        move(db, line.item_id, "issue", -body.qty, reason=f"{ro.number}: {line.description}",
             source_type="repair_order_line", source_id=line.id)
    except StockError as e:
        raise HTTPException(409, str(e))
    line.issued_qty += body.qty
    _log(db, ro, "parts", f"Issued {body.qty.normalize():f} x {line.description}", line_id=line.id)
    db.commit()
    return repair_order_out(db, ro)


@router.post("/repair-orders/{ro_id}/lines/{line_id}/return")
def return_part(ro_id: uuid.UUID, line_id: uuid.UUID, body: QtyIn, actor: Actor = Depends(can_repair),
                db: Session = Depends(get_db)):
    """An unused part goes back at the cost it left at, so stock value is unchanged.
    Allowed through Ready so unused parts can be corrected before the invoice."""
    ro = _get_ro(db, actor, ro_id, lock=True)
    _require_working(db, ro)
    _refuse_stage(ro, "return parts to stock", {"received", "in_repair", "testing", "ready"})
    line = _line(ro, line_id)
    if body.qty > line.issued_qty:
        raise HTTPException(422, f"Only {line.issued_qty.normalize():f} were issued on this line")
    out_qty, out_value = db.execute(select(func.sum(-StockMovement.qty), func.sum(-StockMovement.qty * StockMovement.unit_cost))
                                    .where(StockMovement.source_type == "repair_order_line", StockMovement.source_id == line.id,
                                           StockMovement.kind == "issue")).one()
    move(db, line.item_id, "return", body.qty, unit_cost=(out_value / out_qty).quantize(Decimal("0.0001")),
         reason=f"{ro.number}: {line.description} not used", source_type="repair_order_line", source_id=line.id)
    line.issued_qty -= body.qty
    if line.issued_qty == 0 and line.state == "done":
        line.state = "pending"
    _log(db, ro, "parts", f"Returned {body.qty.normalize():f} x {line.description} to stock", line_id=line.id)
    db.commit()
    return repair_order_out(db, ro)


# --- activity ----------------------------------------------------------------------------------

class ActivityIn(BaseModel):
    kind: Literal["finding", "note", "customer_update"]
    body: Text = Field(min_length=2, max_length=3000)
    line_id: uuid.UUID | None = None
    photo_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


@router.post("/repair-orders/{ro_id}/activity", status_code=201)
def add_activity(ro_id: uuid.UUID, body: ActivityIn, actor: Actor = Depends(can_repair), db: Session = Depends(get_db)):
    ro = _get_ro(db, actor, ro_id)
    _require_working(db, ro)
    if body.line_id:
        _line(ro, body.line_id)
    entry = _log(db, ro, body.kind, body.body, line_id=body.line_id, customer_visible=body.kind == "customer_update")
    db.flush()
    _attach(db, actor, body.photo_ids, "ro_activity", entry.id)
    db.commit()
    return repair_order_out(db, ro)
