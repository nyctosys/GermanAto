"""Turning punches into days: present, late, absent, off, on leave. Used by the
attendance screens and by payroll, so both always agree."""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import TIMEZONE
from app.models import DayMark, Employee, Punch

TZ = ZoneInfo(TIMEZONE)
GRACE_MINUTES = 15  # arriving this much after the shift starts is not yet late


@dataclass
class Day:
    day: date
    status: str  # present, late, incomplete, absent, off, paid_leave, unpaid_leave
    first: datetime | None = None
    last: datetime | None = None
    hours: Decimal = Decimal(0)
    punches: int = 0
    note: str = ""


@dataclass
class Totals:
    present: int = 0
    late: int = 0
    absent: int = 0
    paid_leave: int = 0
    unpaid_leave: int = 0
    off: int = 0
    incomplete: int = 0
    working_days: int = 0  # days the person was expected to work (not their weekly off)
    hours: Decimal = Decimal(0)
    days: list[Day] = field(default_factory=list)


def local(dt: datetime) -> datetime:
    return dt.astimezone(TZ)


def month_range(month: str) -> tuple[date, date]:
    start = date.fromisoformat(f"{month}-01")
    nxt = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, nxt - timedelta(days=1)


def summarise(db: Session, e: Employee, start: date, end: date, today: date | None = None) -> Totals:
    """One employee's days between start and end (never beyond today, or before they joined or after they left)."""
    today = today or datetime.now(TZ).date()
    first_day, last_day = max(start, e.joined_on), min(end, today, e.left_on or end)
    lo = datetime.combine(first_day, datetime.min.time(), TZ)
    hi = datetime.combine(last_day + timedelta(days=1), datetime.min.time(), TZ)
    by_day: dict[date, list[datetime]] = {}
    for p in db.scalars(select(Punch).where(Punch.employee_id == e.id, Punch.voided.is_(False), Punch.punched_at >= lo, Punch.punched_at < hi)
                        .order_by(Punch.punched_at)):
        by_day.setdefault(local(p.punched_at).date(), []).append(local(p.punched_at))
    marks = {m.day: m for m in db.scalars(select(DayMark).where(DayMark.employee_id == e.id, DayMark.day >= first_day, DayMark.day <= last_day))}
    t = Totals()
    d = first_day
    while d <= last_day:
        punches = by_day.get(d, [])
        if d in marks:
            day = Day(d, marks[d].kind, punches=len(punches), note=marks[d].reason)
            t.paid_leave += day.status == "paid_leave"
            t.unpaid_leave += day.status == "unpaid_leave"
            t.working_days += d.weekday() != e.weekly_off
        elif not punches:
            off = d.weekday() == e.weekly_off
            day = Day(d, "off" if off else "absent")
            t.off += off
            t.absent += not off
            t.working_days += not off
        else:
            first, last = punches[0], punches[-1]
            late = first.time() > (datetime.combine(d, e.shift_start) + timedelta(minutes=GRACE_MINUTES)).time()
            hours = Decimal(str(round((last - first).total_seconds() / 3600, 2))) if len(punches) > 1 else Decimal(0)
            status = "incomplete" if len(punches) == 1 else "late" if late else "present"
            day = Day(d, status, first, last, hours, len(punches))
            t.present += status in ("present", "incomplete")
            t.late += status == "late"
            t.incomplete += status == "incomplete"
            t.hours += hours
            t.working_days += d.weekday() != e.weekly_off
        t.days.append(day)
        d += timedelta(days=1)
    return t
