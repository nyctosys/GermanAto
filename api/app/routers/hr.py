"""Employees, attendance devices and attendance (spec §HR)."""

import hashlib
import secrets
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app import attendance
from app.auth import Actor, require
from app.db import get_db
from app.models import AttendanceDevice, DayMark, Employee, Punch, User
from app.numbering import next_number
from app.validators import Cnic, Name, Phone, Text

router = APIRouter(prefix="/api", tags=["hr"])
can_hr = require("hr")


def _get(db: Session, actor: Actor, model, id_: uuid.UUID, label: str):
    obj = db.get(model, id_)
    if not obj or obj.branch_id != actor.branch.id:
        raise HTTPException(404, f"{label} not found")
    return obj


# --- employees -----------------------------------------------------------------------------------------

class EmployeeIn(BaseModel):
    full_name: Name
    title: Text = Field(default="", max_length=80)
    phone: Phone = ""
    cnic: Cnic = ""
    user_id: uuid.UUID | None = None
    device_pin: Text = Field(default="", max_length=20)
    monthly_salary: Decimal = Field(default=Decimal(0), ge=0, le=100_000_000, decimal_places=2)
    shift_start: time = time(9, 0)
    shift_end: time = time(18, 0)
    weekly_off: int = Field(default=6, ge=0, le=6)
    joined_on: date
    notes: Text = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def shift_makes_sense(self):
        if self.shift_end <= self.shift_start:
            raise ValueError("The shift must end after it starts")
        if self.joined_on > date.today() + timedelta(days=31):
            raise ValueError("The joining date is too far ahead")
        return self


class EmployeeUpdate(EmployeeIn):
    left_on: date | None = None
    is_active: bool = True
    version: int


def employee_out(e: Employee, user: User | None = None) -> dict:
    data = {k: getattr(e, k) for k in ("id", "number", "full_name", "title", "phone", "cnic", "user_id", "device_pin", "monthly_salary",
                                       "shift_start", "shift_end", "weekly_off", "joined_on", "left_on", "notes", "is_active", "version")}
    data["username"] = user.username if user else None
    return data


def _check_unique(db: Session, actor: Actor, body: EmployeeIn, own: uuid.UUID | None) -> None:
    def taken(col, value):
        stmt = select(Employee.id).where(Employee.branch_id == actor.branch.id, col == value)
        return db.scalar(stmt.where(Employee.id != own) if own else stmt) is not None
    if body.cnic and taken(Employee.cnic, body.cnic):
        raise HTTPException(409, "An employee with this CNIC already exists")
    if body.device_pin and taken(Employee.device_pin, body.device_pin):
        raise HTTPException(409, f"Device number {body.device_pin} already belongs to another employee")
    if body.user_id:
        u = db.get(User, body.user_id)
        if not u:
            raise HTTPException(404, "User not found")
        if db.scalar(select(Employee.id).where(Employee.user_id == body.user_id, *( [Employee.id != own] if own else [] ))):
            raise HTTPException(409, "That login already belongs to another employee")


def _link_punches(db: Session, actor: Actor, e: Employee) -> int:
    """Punches that arrived for a device number nobody owned now belong to this employee."""
    if not e.device_pin:
        return 0
    res = db.execute(update(Punch).where(Punch.branch_id == actor.branch.id, Punch.employee_id.is_(None), Punch.device_pin == e.device_pin)
                     .values(employee_id=e.id))
    return res.rowcount or 0


@router.get("/employees")
def list_employees(q: str = "", include_inactive: bool = False, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    stmt = select(Employee, User).outerjoin(User, User.id == Employee.user_id).where(Employee.branch_id == actor.branch.id).order_by(Employee.full_name)
    if not include_inactive:
        stmt = stmt.where(Employee.is_active)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Employee.full_name.ilike(like), Employee.number.ilike(like), Employee.phone.ilike(like), Employee.title.ilike(like)))
    return [employee_out(e, u) for e, u in db.execute(stmt)]


@router.post("/employees", status_code=201)
def create_employee(body: EmployeeIn, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    _check_unique(db, actor, body, None)
    e = Employee(number=next_number(db, actor.branch, "employee"), **body.model_dump())
    db.add(e)
    db.flush()
    _link_punches(db, actor, e)
    db.commit()
    return employee_out(e, db.get(User, e.user_id) if e.user_id else None)


@router.get("/employees/{employee_id}")
def get_employee(employee_id: uuid.UUID, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    e = _get(db, actor, Employee, employee_id, "Employee")
    return employee_out(e, db.get(User, e.user_id) if e.user_id else None)


@router.put("/employees/{employee_id}")
def update_employee(employee_id: uuid.UUID, body: EmployeeUpdate, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    e = _get(db, actor, Employee, employee_id, "Employee")
    if body.version != e.version:
        raise HTTPException(409, "Someone else changed this employee. Reload and try again.")
    if body.left_on and body.left_on < body.joined_on:
        raise HTTPException(422, "They can't leave before they joined")
    _check_unique(db, actor, body, e.id)
    for k, v in body.model_dump(exclude={"version"}).items():
        setattr(e, k, v)
    db.flush()
    _link_punches(db, actor, e)
    db.commit()
    return employee_out(e, db.get(User, e.user_id) if e.user_id else None)


@router.get("/employee-logins")
def available_logins(actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    """Active users with no employee record yet, to link a login to an employee."""
    taken = select(Employee.user_id).where(Employee.user_id.is_not(None))
    return [{"id": u.id, "username": u.username, "full_name": u.full_name}
            for u in db.scalars(select(User).where(User.is_active, User.id.not_in(taken)).order_by(User.full_name))]


# --- attendance devices --------------------------------------------------------------------------------

def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def device_out(d: AttendanceDevice, secret: str | None = None) -> dict:
    out = {"id": d.id, "serial": d.serial, "name": d.name, "is_active": d.is_active, "has_secret": bool(d.secret_hash),
           "last_seen_at": d.last_seen_at, "version": d.version}
    if secret:
        out["secret"] = secret  # shown once, here only
    return out


class DeviceIn(BaseModel):
    serial: Text = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: Name = Field(max_length=80)
    use_secret: bool = False


@router.get("/attendance-devices")
def list_devices(actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    return [device_out(d) for d in db.scalars(select(AttendanceDevice).where(AttendanceDevice.branch_id == actor.branch.id).order_by(AttendanceDevice.name))]


@router.post("/attendance-devices", status_code=201)
def register_device(body: DeviceIn, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    """Registers a terminal. Anything not registered here is refused when it tries to push punches."""
    if db.scalar(select(AttendanceDevice.id).where(AttendanceDevice.serial == body.serial)):
        raise HTTPException(409, "A device with this serial number is already registered")
    secret = secrets.token_urlsafe(18) if body.use_secret else None
    d = AttendanceDevice(serial=body.serial, name=body.name, secret_hash=_hash(secret) if secret else "")
    db.add(d)
    db.commit()
    return device_out(d, secret)


class DeviceUpdate(BaseModel):
    name: Name = Field(max_length=80)
    is_active: bool
    version: int


@router.put("/attendance-devices/{device_id}")
def update_device(device_id: uuid.UUID, body: DeviceUpdate, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    d = _get(db, actor, AttendanceDevice, device_id, "Device")
    if body.version != d.version:
        raise HTTPException(409, "Someone else changed this device. Reload and try again.")
    d.name, d.is_active = body.name, body.is_active
    db.commit()
    return device_out(d)


@router.post("/attendance-devices/{device_id}/secret")
def new_secret(device_id: uuid.UUID, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    """Replaces the shared secret. The old one stops working at once."""
    d = _get(db, actor, AttendanceDevice, device_id, "Device")
    secret = secrets.token_urlsafe(18)
    d.secret_hash = _hash(secret)
    db.commit()
    return device_out(d, secret)


# --- attendance ----------------------------------------------------------------------------------------

def _month(month: str | None) -> str:
    month = month or datetime.now(attendance.TZ).strftime("%Y-%m")
    try:
        attendance.month_range(month)
    except ValueError:
        raise HTTPException(422, "Use a month like 2026-10")
    return month


def totals_out(t: attendance.Totals, days: bool) -> dict:
    out = {"present": t.present, "late": t.late, "absent": t.absent, "paid_leave": t.paid_leave, "unpaid_leave": t.unpaid_leave,
           "off": t.off, "incomplete": t.incomplete, "working_days": t.working_days, "hours": t.hours}
    if days:
        out["days"] = [{"day": d.day, "status": d.status, "first": d.first, "last": d.last, "hours": d.hours, "punches": d.punches, "note": d.note}
                       for d in t.days]
    return out


@router.get("/attendance")
def monthly(month: str | None = None, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    month = _month(month)
    start, end = attendance.month_range(month)
    emps = db.scalars(select(Employee).where(Employee.branch_id == actor.branch.id, Employee.joined_on <= end,
                                             or_(Employee.left_on.is_(None), Employee.left_on >= start)).order_by(Employee.full_name)).all()
    return {"month": month, "employees": [{"employee": {"id": e.id, "number": e.number, "full_name": e.full_name, "title": e.title},
                                           **totals_out(attendance.summarise(db, e, start, end), False)} for e in emps]}


@router.get("/attendance/unmatched")
def unmatched(actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    """Device numbers that punched but belong to nobody yet: give the number to an employee to claim them."""
    rows = db.execute(select(Punch.device_pin, func.count(), func.max(Punch.punched_at)).where(
        Punch.branch_id == actor.branch.id, Punch.employee_id.is_(None), Punch.voided.is_(False)).group_by(Punch.device_pin)).all()
    return [{"device_pin": pin, "punches": n, "last": last} for pin, n, last in rows]


@router.get("/attendance/{employee_id}")
def one_month(employee_id: uuid.UUID, month: str | None = None, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    e = _get(db, actor, Employee, employee_id, "Employee")
    month = _month(month)
    start, end = attendance.month_range(month)
    punches = db.scalars(select(Punch).where(Punch.employee_id == e.id, Punch.punched_at >= datetime.combine(start, time.min, attendance.TZ),
                                             Punch.punched_at < datetime.combine(end + timedelta(days=1), time.min, attendance.TZ))
                         .order_by(Punch.punched_at.desc())).all()
    return {"month": month, "employee": employee_out(e), **totals_out(attendance.summarise(db, e, start, end), True),
            "punches": [{"id": p.id, "at": p.punched_at, "source": p.source, "reason": p.reason, "voided": p.voided} for p in punches]}


class ManualPunch(BaseModel):
    employee_id: uuid.UUID
    punched_at: datetime
    reason: Text = Field(min_length=5, max_length=500)


@router.post("/attendance/punches", status_code=201)
def manual_punch(body: ManualPunch, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    """A forgotten or failed punch entered by hand. It says so, and why."""
    e = _get(db, actor, Employee, body.employee_id, "Employee")
    when = body.punched_at if body.punched_at.tzinfo else body.punched_at.replace(tzinfo=attendance.TZ)
    if when > datetime.now(attendance.TZ) + timedelta(minutes=5):
        raise HTTPException(422, "A punch can't be in the future")
    if when.date() < e.joined_on:
        raise HTTPException(422, "That is before they joined")
    p = Punch(employee_id=e.id, punched_at=when, source="manual", reason=body.reason, device_pin=e.device_pin)
    db.add(p)
    db.commit()
    return {"id": p.id}


class VoidPunch(BaseModel):
    reason: Text = Field(min_length=3, max_length=500)


@router.post("/attendance/punches/{punch_id}/void")
def void_punch(punch_id: uuid.UUID, body: VoidPunch, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    p = _get(db, actor, Punch, punch_id, "Punch")
    if p.source != "manual":
        raise HTTPException(409, "A punch from the device can't be removed. Add a manual punch or mark the day instead.")
    if p.voided:
        raise HTTPException(409, "Already voided")
    p.voided, p.reason = True, f"{p.reason} | Voided: {body.reason}"
    db.commit()
    return {"ok": True}


class MarkIn(BaseModel):
    employee_id: uuid.UUID
    day: date
    kind: Literal["paid_leave", "unpaid_leave"]
    reason: Text = Field(min_length=3, max_length=500)


@router.post("/attendance/marks", status_code=201)
def mark_day(body: MarkIn, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    e = _get(db, actor, Employee, body.employee_id, "Employee")
    if body.day < e.joined_on:
        raise HTTPException(422, "That is before they joined")
    mark = db.scalar(select(DayMark).where(DayMark.employee_id == e.id, DayMark.day == body.day))
    if mark:
        mark.kind, mark.reason = body.kind, body.reason
    else:
        db.add(DayMark(employee_id=e.id, day=body.day, kind=body.kind, reason=body.reason))
    db.commit()
    return {"ok": True}


@router.delete("/attendance/marks")
def unmark_day(employee_id: uuid.UUID, day: date, actor: Actor = Depends(can_hr), db: Session = Depends(get_db)):
    e = _get(db, actor, Employee, employee_id, "Employee")
    mark = db.scalar(select(DayMark).where(DayMark.employee_id == e.id, DayMark.day == day))
    if not mark:
        raise HTTPException(404, "That day isn't marked")
    db.delete(mark)
    db.commit()
    return {"ok": True}
