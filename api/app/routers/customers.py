"""Customers, cars, ownership transfers and car history (spec R2, R7)."""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import Actor, require
from app.db import get_db
from app.models import Attachment, AuditLog, Car, CarOwnership, Customer, User
from app.numbering import next_number
from app.validators import Cnic, Email, Name, Phone, Text, Upper, Vin, normalize_plate

router = APIRouter(prefix="/api", tags=["customers"])
can_view = require("customers")

FUELS = Literal["petrol", "diesel", "hybrid", "ev", "cng", "other"]


# --- schemas ---------------------------------------------------------------

class CustomerIn(BaseModel):
    kind: Literal["individual", "company"] = "individual"
    name: Name
    phone: Phone = Field(min_length=1)
    phone_alt: Phone = ""
    email: Email = ""
    cnic: Cnic = ""
    address: Text = Field(default="", max_length=300)
    notes: Text = Field(default="", max_length=2000)
    whatsapp_opt_out: bool = False
    allow_duplicate_phone: bool = False  # the form asks first, then resends with this set


class CustomerUpdate(CustomerIn):
    version: int
    is_active: bool = True


class CarIn(BaseModel):
    plate: Upper = Field(default="", max_length=20)
    vin: Vin = ""
    chassis_no: Upper = Field(default="", max_length=40)
    engine_no: Upper = Field(default="", max_length=40)
    make: Name
    model: Text = Field(default="", max_length=60)
    year: int | None = Field(default=None, ge=1950, le=date.today().year + 1)
    color: Text = Field(default="", max_length=40)
    fuel: FUELS = "petrol"
    odometer_km: int | None = Field(default=None, ge=0, le=3_000_000)
    notes: Text = Field(default="", max_length=2000)


class CarCreate(CarIn):
    owner_id: uuid.UUID


class CarUpdate(CarIn):
    version: int


class TransferIn(BaseModel):
    to_customer_id: uuid.UUID
    on: date
    reason: Text = Field(min_length=3, max_length=300)
    odometer_km: int | None = Field(default=None, ge=0, le=3_000_000)
    attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


def customer_out(c: Customer) -> dict:
    return {k: getattr(c, k) for k in ("id", "number", "kind", "name", "phone", "phone_alt", "email", "cnic",
                                       "address", "notes", "whatsapp_opt_out", "is_active", "version", "created_at")}


def car_out(c: Car, owner: Customer | None = None) -> dict:
    data = {k: getattr(c, k) for k in ("id", "plate", "vin", "chassis_no", "engine_no", "make", "model", "year",
                                       "color", "fuel", "odometer_km", "notes", "version", "created_at")}
    data["owner"] = {"id": owner.id, "name": owner.name, "number": owner.number, "phone": owner.phone} if owner else None
    return data


def _current_owner(db: Session, car_id: uuid.UUID) -> Customer | None:
    return db.scalar(select(Customer).join(CarOwnership, CarOwnership.customer_id == Customer.id)
                     .where(CarOwnership.car_id == car_id, CarOwnership.until.is_(None)))


def _get(db: Session, model, obj_id: uuid.UUID, what: str):
    obj = db.get(model, obj_id)
    if not obj:
        raise HTTPException(404, f"{what} not found")
    return obj


def _check_car_unique(db: Session, body: CarIn, exclude: uuid.UUID | None = None) -> str:
    plate_norm = normalize_plate(body.plate)
    for column, value, label in ((Car.plate_norm, plate_norm, "plate"), (Car.vin, body.vin, "VIN")):
        if not value:
            continue
        q = select(Car).where(column == value)
        if exclude:
            q = q.where(Car.id != exclude)
        if other := db.scalar(q):
            raise HTTPException(409, f"Another car already has this {label}: {other.make} {other.model} {other.plate}".strip())
    return plate_norm


# --- customers -------------------------------------------------------------

@router.get("/customers")
def list_customers(q: str = "", limit: int = Query(50, ge=1, le=200), include_inactive: bool = False,
                   _: Actor = Depends(can_view), db: Session = Depends(get_db)):
    stmt = select(Customer).order_by(Customer.name).limit(limit)
    if not include_inactive:
        stmt = stmt.where(Customer.is_active)
    if q.strip():
        like = f"%{q.strip()}%"
        digits = "".join(ch for ch in q if ch.isdigit())
        conds = [Customer.name.ilike(like), Customer.number.ilike(like), Customer.email.ilike(like)]
        if len(digits) >= 4:  # "0300 123" should find +92300123...
            conds += [Customer.phone.contains(digits.lstrip("0")), Customer.phone_alt.contains(digits.lstrip("0"))]
        plate = normalize_plate(q)
        if plate:
            conds.append(Customer.id.in_(
                select(CarOwnership.customer_id).join(Car, Car.id == CarOwnership.car_id)
                .where(CarOwnership.until.is_(None), Car.plate_norm.contains(plate))))
        stmt = stmt.where(or_(*conds))
    return [customer_out(c) for c in db.scalars(stmt)]


@router.post("/customers", status_code=201)
def create_customer(body: CustomerIn, actor: Actor = Depends(can_view), db: Session = Depends(get_db)):
    if not body.allow_duplicate_phone:
        same = db.scalars(select(Customer).where(Customer.phone == body.phone).limit(3)).all()
        if same:
            raise HTTPException(409, {"code": "duplicate_phone", "message": "A customer with this phone already exists",
                                      "matches": jsonable_encoder([customer_out(c) for c in same])})
    customer = Customer(number=next_number(db, actor.branch, "customer"),
                        **body.model_dump(exclude={"allow_duplicate_phone"}))
    db.add(customer)
    db.commit()
    return customer_out(customer)


@router.get("/customers/{customer_id}")
def get_customer(customer_id: uuid.UUID, _: Actor = Depends(can_view), db: Session = Depends(get_db)):
    customer = _get(db, Customer, customer_id, "Customer")
    owned = db.execute(select(Car, CarOwnership).join(CarOwnership, CarOwnership.car_id == Car.id)
                       .where(CarOwnership.customer_id == customer.id).order_by(CarOwnership.since.desc())).all()
    return {**customer_out(customer),
            "cars": [{**car_out(car), "since": own.since, "until": own.until} for car, own in owned]}


@router.put("/customers/{customer_id}")
def update_customer(customer_id: uuid.UUID, body: CustomerUpdate, _: Actor = Depends(can_view),
                    db: Session = Depends(get_db)):
    customer = _get(db, Customer, customer_id, "Customer")
    if body.version != customer.version:
        raise HTTPException(409, "Someone else changed this customer. Reload and try again.")
    for key, value in body.model_dump(exclude={"version", "allow_duplicate_phone"}).items():
        setattr(customer, key, value)
    db.commit()
    return customer_out(customer)


# --- cars --------------------------------------------------------------------

@router.get("/cars")
def list_cars(q: str = "", limit: int = Query(50, ge=1, le=200), _: Actor = Depends(can_view),
              db: Session = Depends(get_db)):
    stmt = (select(Car, Customer).outerjoin(CarOwnership, (CarOwnership.car_id == Car.id) & CarOwnership.until.is_(None))
            .outerjoin(Customer, Customer.id == CarOwnership.customer_id).order_by(Car.make, Car.model).limit(limit))
    if q.strip():
        like, plate = f"%{q.strip()}%", normalize_plate(q)
        conds = [Car.make.ilike(like), Car.model.ilike(like), Customer.name.ilike(like), Car.chassis_no.ilike(like)]
        if plate:
            conds += [Car.plate_norm.contains(plate), Car.vin.contains(plate)]
        stmt = stmt.where(or_(*conds))
    return [car_out(car, owner) for car, owner in db.execute(stmt)]


@router.post("/cars", status_code=201)
def create_car(body: CarCreate, _: Actor = Depends(can_view), db: Session = Depends(get_db)):
    _get(db, Customer, body.owner_id, "Owner")
    plate_norm = _check_car_unique(db, body)
    car = Car(plate_norm=plate_norm, **body.model_dump(exclude={"owner_id"}))
    db.add(car)
    db.flush()
    db.add(CarOwnership(car_id=car.id, customer_id=body.owner_id, since=date.today(), reason="First registered",
                        odometer_km=body.odometer_km))
    db.commit()
    return car_out(car, db.get(Customer, body.owner_id))


@router.get("/cars/{car_id}")
def get_car(car_id: uuid.UUID, actor: Actor = Depends(can_view), db: Session = Depends(get_db)):
    car = _get(db, Car, car_id, "Car")
    owners = db.execute(select(CarOwnership, Customer).join(Customer, Customer.id == CarOwnership.customer_id)
                        .where(CarOwnership.car_id == car.id).order_by(CarOwnership.since.desc(), CarOwnership.created_at.desc())).all()
    proofs = {}
    for a in db.scalars(select(Attachment).where(Attachment.entity_type == "car_ownerships",
                                                 Attachment.entity_id.in_([o.id for o, _ in owners]))):
        proofs.setdefault(a.entity_id, []).append({"id": a.id, "name": a.original_name, "url": f"/api/attachments/{a.id}/file"})
    current = next((c for o, c in owners if o.until is None), None)
    return {
        **car_out(car, current),
        "ownerships": [{"id": o.id, "since": o.since, "until": o.until, "reason": o.reason, "odometer_km": o.odometer_km,
                        "customer": {"id": c.id, "name": c.name, "number": c.number, "phone": c.phone},
                        "proofs": proofs.get(o.id, [])} for o, c in owners],
    }


@router.put("/cars/{car_id}")
def update_car(car_id: uuid.UUID, body: CarUpdate, _: Actor = Depends(can_view), db: Session = Depends(get_db)):
    car = _get(db, Car, car_id, "Car")
    if body.version != car.version:
        raise HTTPException(409, "Someone else changed this car. Reload and try again.")
    car.plate_norm = _check_car_unique(db, body, exclude=car.id)
    for key, value in body.model_dump(exclude={"version"}).items():
        setattr(car, key, value)
    db.commit()
    return car_out(car, _current_owner(db, car.id))


@router.post("/cars/{car_id}/transfer")
def transfer_car(car_id: uuid.UUID, body: TransferIn, actor: Actor = Depends(require("car-transfer")),
                 db: Session = Depends(get_db)):
    car = db.scalar(select(Car).where(Car.id == car_id).with_for_update())
    if not car:
        raise HTTPException(404, "Car not found")
    _get(db, Customer, body.to_customer_id, "New owner")
    current = db.scalar(select(CarOwnership).where(CarOwnership.car_id == car.id, CarOwnership.until.is_(None)))
    if current and current.customer_id == body.to_customer_id:
        raise HTTPException(409, "The car already belongs to this customer")
    if current and body.on < current.since:
        raise HTTPException(422, f"The transfer date can't be before the current owner got the car ({current.since})")
    if body.on > date.today():
        raise HTTPException(422, "The transfer date can't be in the future")
    proofs = db.scalars(select(Attachment).where(Attachment.id.in_(body.attachment_ids),
                                                 Attachment.branch_id == actor.branch.id)).all()
    if len(proofs) != len(set(body.attachment_ids)):
        raise HTTPException(422, "One of the proof files wasn't found")
    # Later phases: refuse while the car has an open visit (spec R7).

    if current:
        current.until = body.on
    ownership = CarOwnership(car_id=car.id, customer_id=body.to_customer_id, since=body.on, reason=body.reason,
                             odometer_km=body.odometer_km)
    db.add(ownership)
    db.flush()
    for proof in proofs:
        proof.entity_type, proof.entity_id = "car_ownerships", ownership.id
    if body.odometer_km and (car.odometer_km or 0) < body.odometer_km:
        car.odometer_km = body.odometer_km
    db.commit()
    return get_car(car.id, actor, db)


@router.get("/cars/{car_id}/history")
def car_history(car_id: uuid.UUID, _: Actor = Depends(can_view), db: Session = Depends(get_db)):
    """Everything that happened to the car, newest first. Visits, inspections
    and invoices join this timeline in Phase 3."""
    car = _get(db, Car, car_id, "Car")
    events: list[dict] = []
    for o, c in db.execute(select(CarOwnership, Customer).join(Customer, Customer.id == CarOwnership.customer_id)
                           .where(CarOwnership.car_id == car.id)):
        # Sorted by when it was recorded (two owners can share a date); shown with the transfer date.
        events.append({"at": o.created_at.isoformat(), "on": o.since.isoformat(), "kind": "ownership",
                       "title": f"Owned by {c.name}", "detail": o.reason, "odometer_km": o.odometer_km,
                       "link": f"/customers/{c.id}"})
    for a, username in db.execute(select(AuditLog, User.username).outerjoin(User, User.id == AuditLog.user_id)
                                  .where(AuditLog.entity_type == "cars", AuditLog.entity_id == car.id,
                                         AuditLog.action == "update")):
        fields = [k for k in a.changes if k not in ("plate_norm",)]
        if fields:
            events.append({"at": a.at.isoformat(), "on": None, "kind": "edit", "title": "Details changed",
                           "detail": ", ".join(f.replace("_", " ") for f in fields) + (f" by {username}" if username else ""),
                           "odometer_km": None, "link": None})
    events.sort(key=lambda e: e["at"], reverse=True)
    return events
