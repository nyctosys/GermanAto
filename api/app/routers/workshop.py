"""Visits (check-in) and vehicle inspections (spec §2, §2.4)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import inspection_template as tpl
from app.auth import Actor, require
from app.db import get_db, utcnow
from app.models import Attachment, Car, CarOwnership, Customer, Inspection, JobCard, Payment, Quotation, User, Visit
from app.numbering import next_number
from app.validators import Text

router = APIRouter(prefix="/api", tags=["workshop"])
can_visit = require("visits")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- inspection answers ---------------------------------------------------------

Rating = Literal["good", "average", "attention", "not_checked"]
Short = Field(default="", max_length=200)


class ItemAnswer(Strict):
    rating: Rating = "not_checked"
    note: str = Field(default="", max_length=500)
    photo_ids: list[uuid.UUID] = Field(default_factory=list, max_length=6)


class Paint(Strict):
    findings: dict[str, Literal["original", "repaint", "filler", "replaced"]] = Field(default_factory=dict, max_length=30)
    notes: str = Field(default="", max_length=1000)
    accident: Literal["none", "repair_signs"] | None = None
    structural_notes: str = Field(default="", max_length=1000)


class Tyre(Strict):
    mm: Decimal | None = Field(default=None, ge=0, le=20)
    pct: int | None = Field(default=None, ge=0, le=100)


class Tyres(Strict):
    fl: Tyre = Field(default_factory=Tyre)
    fr: Tyre = Field(default_factory=Tyre)
    rl: Tyre = Field(default_factory=Tyre)
    rr: Tyre = Field(default_factory=Tyre)
    spare: str = Short
    wheel_damage: bool | None = None


class Dtc(Strict):
    module: str = Field(max_length=60)
    code: str = Field(max_length=20)
    description: str = Field(default="", max_length=300)
    priority: Literal["high", "medium", "low"] = "medium"


class Scan(Strict):
    tool: str = Short
    scanned_on: date | None = None
    battery_rest_v: Decimal | None = Field(default=None, ge=0, le=20)
    battery_running_v: Decimal | None = Field(default=None, ge=0, le=20)
    warning_lights: list[Literal["check_engine", "abs", "airbag", "chassis", "other"]] = Field(default_factory=list)
    other_light: str = Short
    dtcs_stored: bool | None = None
    modules_not_communicating: str = Short
    dtcs: list[Dtc] = Field(default_factory=list, max_length=50)


OkIssue = Literal["ok", "issue"] | None


class Ev(Strict):
    soc_pct: Decimal | None = Field(default=None, ge=0, le=100)
    soh_pct: Decimal | None = Field(default=None, ge=0, le=100)
    capacity_kwh: Decimal | None = Field(default=None, ge=0, le=300)
    pack_voltage: Decimal | None = Field(default=None, ge=0, le=1500)
    cell_imbalance_mv: Decimal | None = Field(default=None, ge=0, le=5000)
    isolation_mohm: Decimal | None = Field(default=None, ge=0, le=100000)
    charging_ac: OkIssue = None
    charging_dc: OkIssue = None
    cooling: OkIssue = None
    notes: str = Field(default="", max_length=1000)


class Repair(Strict):
    priority: Literal["high", "medium", "low"] = "medium"
    repair: str = Field(min_length=1, max_length=200)
    remarks: str = Field(default="", max_length=300)
    estimated_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    sent_to_job_card: bool = False


class Assessment(Strict):
    overall: Literal["excellent", "good", "average", "poor"] | None = None
    recommendation: Literal["recommended", "after_repairs", "not_recommended"] | None = None
    budget: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    summary: str = Field(default="", max_length=3000)
    odometer_km: int | None = Field(default=None, ge=0, le=3_000_000)


class InspectionData(Strict):
    """The inspector's findings only. Vehicle and customer details are never
    stored here: they come from the central car and customer records, and
    are copied into `snapshot` by the server when the report is signed."""

    items: dict[str, ItemAnswer] = Field(default_factory=dict)
    bulk_marked: list[str] = Field(default_factory=list)  # sections filled with "Mark section Good"
    paint: Paint = Field(default_factory=Paint)
    tyres: Tyres = Field(default_factory=Tyres)
    scan: Scan = Field(default_factory=Scan)
    ev: Ev = Field(default_factory=Ev)
    repairs: list[Repair] = Field(default_factory=list, max_length=40)
    assessment: Assessment = Field(default_factory=Assessment)
    customer_ack_name: str = Short

    @model_validator(mode="before")
    @classmethod
    def drop_server_fields(cls, v):
        # "snapshot" is written by the server at signing; "details" was the old
        # per-inspection copy of the vehicle. Neither is accepted from a client.
        if isinstance(v, dict):
            v = {k: val for k, val in v.items() if k not in ("snapshot", "details")}
        return v

    @field_validator("items")
    @classmethod
    def known_items(cls, v: dict) -> dict:
        unknown = set(v) - tpl.ITEM_KEYS
        if unknown:
            raise ValueError(f"Unknown checklist items: {', '.join(sorted(unknown))}")
        return v


# --- visits ---------------------------------------------------------------------

class VisitIn(BaseModel):
    car_id: uuid.UUID
    kind: Literal["workshop", "pre_purchase"] = "workshop"
    buyer_id: uuid.UUID | None = None  # required for pre-purchase
    odometer_in: int | None = Field(default=None, ge=0, le=3_000_000)
    fuel_eighths: int | None = Field(default=None, ge=0, le=8)
    complaint: Text = Field(default="", max_length=3000)
    items_left: Text = Field(default="", max_length=1000)
    condition_notes: Text = Field(default="", max_length=3000)
    photo_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)
    signature_id: uuid.UUID | None = None


class VisitUpdate(BaseModel):
    odometer_in: int | None = Field(default=None, ge=0, le=3_000_000)
    fuel_eighths: int | None = Field(default=None, ge=0, le=8)
    complaint: Text = Field(default="", max_length=3000)
    items_left: Text = Field(default="", max_length=1000)
    condition_notes: Text = Field(default="", max_length=3000)
    photo_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)
    signature_id: uuid.UUID | None = None
    version: int


def _attach(db: Session, actor: Actor, ids: list[uuid.UUID], entity_type: str, entity_id: uuid.UUID) -> None:
    found = db.scalars(select(Attachment).where(Attachment.id.in_(ids), Attachment.branch_id == actor.branch.id)).all()
    if len(found) != len(set(ids)):
        raise HTTPException(422, "One of the photos wasn't found. Upload it again.")
    for a in found:
        if a.entity_id and a.entity_id != entity_id:
            raise HTTPException(422, "A photo is already attached to another record")
        a.entity_type, a.entity_id = entity_type, entity_id


def _files(db: Session, entity_type: str, entity_id: uuid.UUID) -> list[dict]:
    return [{"id": a.id, "name": a.original_name, "mime": a.mime, "url": f"/api/attachments/{a.id}/file", "note": a.note}
            for a in db.scalars(select(Attachment).where(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id)
                                .order_by(Attachment.created_at))]


def _get_visit(db: Session, actor: Actor, visit_id: uuid.UUID, *, lock: bool = False) -> Visit:
    q = select(Visit).where(Visit.id == visit_id)
    visit = db.scalar(q.with_for_update() if lock else q)
    if not visit or visit.branch_id != actor.branch.id:
        raise HTTPException(404, "Visit not found")
    return visit


def _require_open(visit: Visit) -> None:
    if visit.status != "open":
        raise HTTPException(409, f"This visit is {visit.status}; nothing more can be added to it")


def person(c: Customer | None) -> dict | None:
    return c and {"id": c.id, "name": c.name, "phone": c.phone, "number": c.number}


def visit_summary(v: Visit, car: Car, customer: Customer, buyer: Customer | None = None) -> dict:
    return {"id": v.id, "number": v.number, "kind": v.kind, "status": v.status, "checked_in_at": v.checked_in_at,
            "closed_at": v.closed_at, "odometer_in": v.odometer_in, "complaint": v.complaint,
            "car": {"id": car.id, "plate": car.plate, "make": car.make, "model": car.model, "year": car.year},
            "customer": person(customer), "buyer": person(buyer)}


@router.post("/visits", status_code=201)
def check_in(body: VisitIn, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    car = db.scalar(select(Car).where(Car.id == body.car_id).with_for_update())
    if not car:
        raise HTTPException(404, "Car not found")
    open_visit = db.scalar(select(Visit).where(Visit.car_id == car.id, Visit.status == "open"))
    if open_visit:
        raise HTTPException(409, {"code": "already_in", "message": f"This car is already checked in ({open_visit.number})",
                                  "visit_id": str(open_visit.id)})
    owner = db.scalar(select(CarOwnership.customer_id).where(CarOwnership.car_id == car.id, CarOwnership.until.is_(None)))
    if not owner:
        raise HTTPException(422, "This car has no owner on file. Add or transfer it to a customer first.")
    if body.kind == "pre_purchase":
        if not body.buyer_id:
            raise HTTPException(422, "Choose the buyer for a pre-purchase inspection")
        if body.buyer_id == owner:
            raise HTTPException(422, "The buyer can't be the car's current owner (the seller)")
        if not db.get(Customer, body.buyer_id):
            raise HTTPException(404, "Buyer not found")
    elif body.buyer_id:
        raise HTTPException(422, "Only pre-purchase visits have a buyer")
    if body.odometer_in is not None and car.odometer_km and body.odometer_in < car.odometer_km:
        raise HTTPException(422, f"The odometer reads less than last time ({car.odometer_km:,} km). Check the reading.")

    visit = Visit(number=next_number(db, actor.branch, "visit"), customer_id=owner,
                  **body.model_dump(exclude={"photo_ids"}))
    db.add(visit)
    db.flush()
    _attach(db, actor, body.photo_ids + ([body.signature_id] if body.signature_id else []), "visits", visit.id)
    if body.odometer_in:
        car.odometer_km = body.odometer_in
    db.commit()
    return get_visit(visit.id, actor, db)


@router.get("/visits")
def list_visits(status: Literal["open", "closed", "cancelled", "all"] = "open", q: str = "",
                limit: int = Query(100, ge=1, le=300), actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    stmt = (select(Visit, Car, Customer).join(Car, Car.id == Visit.car_id).join(Customer, Customer.id == Visit.customer_id)
            .where(Visit.branch_id == actor.branch.id).order_by(Visit.checked_in_at.desc()).limit(limit))
    if status != "all":
        stmt = stmt.where(Visit.status == status)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Visit.number.ilike(like), Car.plate.ilike(like), Customer.name.ilike(like),
                              Car.make.ilike(like), Car.model.ilike(like)))
    return [visit_summary(v, car, c, db.get(Customer, v.buyer_id) if v.buyer_id else None) for v, car, c in db.execute(stmt)]


@router.get("/visits/{visit_id}")
def get_visit(visit_id: uuid.UUID, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    v = _get_visit(db, actor, visit_id)
    car, customer = db.get(Car, v.car_id), db.get(Customer, v.customer_id)
    buyer = db.get(Customer, v.buyer_id) if v.buyer_id else None
    inspections = db.scalars(select(Inspection).where(Inspection.visit_id == v.id).order_by(Inspection.created_at)).all()
    files = _files(db, "visits", v.id)
    job_card = db.scalar(select(JobCard).where(JobCard.visit_id == v.id))
    quotes = db.scalars(select(Quotation).where(Quotation.visit_id == v.id).order_by(Quotation.revision)).all()
    payments = db.scalars(select(Payment).where(Payment.visit_id == v.id).order_by(Payment.received_at)).all()
    return {
        **visit_summary(v, car, customer, buyer),
        "fuel_eighths": v.fuel_eighths, "items_left": v.items_left, "condition_notes": v.condition_notes,
        "odometer_out": v.odometer_out, "close_note": v.close_note, "version": v.version,
        "photos": [f for f in files if f["id"] != v.signature_id],
        "signature": next((f for f in files if f["id"] == v.signature_id), None),
        "inspections": [{"id": i.id, "number": i.number, "kind": i.kind, "status": i.status, "signed_at": i.signed_at,
                         "supersedes_id": i.supersedes_id} for i in inspections],
        "job_card": job_card and {"id": job_card.id, "number": job_card.number, "lines": len(job_card.lines)},
        "quotations": [{"id": q.id, "number": q.number, "revision": q.revision, "status": q.status,
                        "expired": q.status == "sent" and q.valid_until < date.today()} for q in quotes],
        "payments": [{"id": p.id, "number": p.number, "kind": p.kind, "status": p.status, "amount": p.amount,
                      "account": p.account, "received_at": p.received_at} for p in payments],
    }


@router.put("/visits/{visit_id}")
def update_visit(visit_id: uuid.UUID, body: VisitUpdate, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    v = _get_visit(db, actor, visit_id)
    _require_open(v)
    if body.version != v.version:
        raise HTTPException(409, "Someone else changed this check-in. Reload and try again.")
    for key, value in body.model_dump(exclude={"version", "photo_ids"}).items():
        setattr(v, key, value)
    _attach(db, actor, body.photo_ids + ([body.signature_id] if body.signature_id else []), "visits", v.id)
    db.commit()
    return get_visit(v.id, actor, db)


class CancelIn(BaseModel):
    reason: Text = Field(min_length=3, max_length=500)


@router.post("/visits/{visit_id}/cancel")
def cancel_visit(visit_id: uuid.UUID, body: CancelIn, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    v = _get_visit(db, actor, visit_id, lock=True)
    _require_open(v)
    if db.scalar(select(Payment.id).where(Payment.visit_id == v.id, Payment.status == "posted")):
        raise HTTPException(409, "Money has been taken on this visit. Refund or void it (admin approval) before cancelling.")
    v.status, v.closed_at, v.close_note = "cancelled", utcnow(), body.reason
    db.commit()
    return get_visit(v.id, actor, db)


# --- inspections -------------------------------------------------------------------

@router.get("/inspection-template")
def inspection_template(_: Actor = Depends(can_visit)):
    return tpl.as_dict()


class StartInspection(BaseModel):
    kind: Literal["workshop", "delivery", "pre_purchase"]


CAR_FIELDS = ("plate", "vin", "engine_no", "make", "model", "year", "color", "fuel")


def snapshot_of(db: Session, v: Visit, car: Car) -> dict:
    """Vehicle and people as they were at signing, so a signed report never
    changes when the central records are edited later."""
    owner, buyer = db.get(Customer, v.customer_id), db.get(Customer, v.buyer_id) if v.buyer_id else None
    return {"car": {k: getattr(car, k) for k in CAR_FIELDS},
            "owner": {"name": owner.name, "phone": owner.phone, "number": owner.number},
            "buyer": buyer and {"name": buyer.name, "phone": buyer.phone, "number": buyer.number}}


def inspection_out(db: Session, i: Inspection) -> dict:
    v, car = db.get(Visit, i.visit_id), db.get(Car, i.car_id)
    inspector = db.get(User, i.inspector_id) if i.inspector_id else None
    sig = {s: (f"/api/attachments/{getattr(i, s)}/file" if getattr(i, s) else None)
           for s in ("inspector_signature_id", "customer_signature_id")}
    return {"id": i.id, "number": i.number, "kind": i.kind, "status": i.status, "template_version": i.template_version,
            "supersedes_id": i.supersedes_id, "data": i.data, "signed_at": i.signed_at, "version": i.version,
            "created_at": i.created_at, "inspector": inspector.full_name if inspector else None,
            "inspector_signature_url": sig["inspector_signature_id"], "customer_signature_url": sig["customer_signature_id"],
            "visit": {"id": v.id, "number": v.number, "kind": v.kind, "odometer_in": v.odometer_in,
                      "car_id": v.car_id, "customer_id": v.customer_id, "buyer_id": v.buyer_id},
            "car": {"id": car.id, **{k: getattr(car, k) for k in CAR_FIELDS}},
            # Live details while drafting; the frozen copy once signed.
            "snapshot": i.data.get("snapshot") or snapshot_of(db, v, car)}


def _get_inspection(db: Session, actor: Actor, inspection_id: uuid.UUID) -> Inspection:
    i = db.get(Inspection, inspection_id)
    if not i or i.branch_id != actor.branch.id:
        raise HTTPException(404, "Inspection not found")
    return i


@router.post("/visits/{visit_id}/inspections", status_code=201)
def start_inspection(visit_id: uuid.UUID, body: StartInspection, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    v = _get_visit(db, actor, visit_id)
    _require_open(v)
    if (body.kind == "pre_purchase") != (v.kind == "pre_purchase"):
        raise HTTPException(422, "Pre-purchase inspections belong to pre-purchase visits, and the other kinds to workshop visits")
    car = db.get(Car, v.car_id)
    data = InspectionData(assessment=Assessment(odometer_km=v.odometer_in))
    i = Inspection(number=next_number(db, actor.branch, "inspection"), kind=body.kind, visit_id=v.id, car_id=car.id,
                   template_version=tpl.VERSION, data=data.model_dump(mode="json"), inspector_id=actor.user.id)
    db.add(i)
    db.commit()
    return inspection_out(db, i)


@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: uuid.UUID, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    return inspection_out(db, _get_inspection(db, actor, inspection_id))


class SaveInspection(BaseModel):
    data: InspectionData
    version: int


@router.put("/inspections/{inspection_id}")
def save_inspection(inspection_id: uuid.UUID, body: SaveInspection, actor: Actor = Depends(can_visit),
                    db: Session = Depends(get_db)):
    """Autosave target: the form sends the whole draft every few seconds."""
    i = _get_inspection(db, actor, inspection_id)
    if i.status != "draft":
        raise HTTPException(409, "This inspection is signed. Start a revision to change it.")
    if body.version != i.version:
        raise HTTPException(409, "This inspection was changed on another device. Reload to continue.")
    i.data = body.data.model_dump(mode="json")
    db.commit()
    return {"version": i.version, "saved_at": i.updated_at}


class SignIn(BaseModel):
    inspector_signature_id: uuid.UUID
    customer_signature_id: uuid.UUID | None = None
    version: int


@router.post("/inspections/{inspection_id}/sign")
def sign_inspection(inspection_id: uuid.UUID, body: SignIn, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    i = _get_inspection(db, actor, inspection_id)
    if i.status != "draft":
        raise HTTPException(409, "Already signed")
    if body.version != i.version:
        raise HTTPException(409, "This inspection was changed on another device. Reload to continue.")
    data = InspectionData.model_validate(i.data)
    if not data.assessment.overall or not data.assessment.recommendation:
        raise HTTPException(422, "Choose the overall condition and the recommendation before signing")
    for key in tpl.ITEM_KEYS:  # anything nobody rated is recorded as not checked, never as good
        data.items.setdefault(key, ItemAnswer())
    _attach(db, actor, [body.inspector_signature_id] + ([body.customer_signature_id] if body.customer_signature_id else []),
            "inspections", i.id)
    i.data = {**data.model_dump(mode="json"),
              "snapshot": jsonable_encoder(snapshot_of(db, db.get(Visit, i.visit_id), db.get(Car, i.car_id)))}
    i.status, i.signed_at, i.inspector_id = "signed", utcnow(), actor.user.id
    i.inspector_signature_id, i.customer_signature_id = body.inspector_signature_id, body.customer_signature_id
    db.commit()
    return inspection_out(db, i)


@router.post("/inspections/{inspection_id}/revise", status_code=201)
def revise_inspection(inspection_id: uuid.UUID, actor: Actor = Depends(can_visit), db: Session = Depends(get_db)):
    """A signed report is never edited: a correction is a new draft that supersedes it."""
    old = _get_inspection(db, actor, inspection_id)
    if old.status != "signed":
        raise HTTPException(409, "Only a signed inspection needs a revision; edit the draft instead")
    if db.scalar(select(Inspection.id).where(Inspection.supersedes_id == old.id)):
        raise HTTPException(409, "This inspection already has a revision")
    findings = {k: v for k, v in old.data.items() if k != "snapshot"}  # a revision re-reads the current records
    new = Inspection(number=next_number(db, actor.branch, "inspection"), kind=old.kind, visit_id=old.visit_id,
                     car_id=old.car_id, template_version=tpl.VERSION, supersedes_id=old.id, data=findings,
                     inspector_id=actor.user.id)
    db.add(new)
    db.commit()
    return inspection_out(db, new)
