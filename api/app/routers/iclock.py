"""The ZKTeco / ADMS push endpoints. A terminal posts punches here without a login, so they are
accepted only from a registered, active serial number, and from one holding the right secret if
the device has one (sent as ?token= or an X-Device-Secret header)."""

import hmac
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import attendance
from app.db import get_db, set_actor, utcnow
from app.models import AttendanceDevice, Employee, Punch
from app.routers.hr import _hash

router = APIRouter(prefix="/iclock", tags=["attendance devices"])


def known_device(db: Session, serial: str, token: str, header: str) -> AttendanceDevice:
    d = db.scalar(select(AttendanceDevice).where(AttendanceDevice.serial == serial))
    if not d or not d.is_active:
        raise HTTPException(403, "Unknown device")
    if d.secret_hash and not hmac.compare_digest(d.secret_hash, _hash(token or header or "")):
        raise HTTPException(403, "Wrong device secret")
    d.last_seen_at = utcnow()
    set_actor(db, branch_id=d.branch_id)
    return d


@router.get("/cdata", response_class=PlainTextResponse)
def handshake(SN: str = Query(...), token: str = "", x_device_secret: str = Header(default=""), db: Session = Depends(get_db)):
    """The terminal's first call: tell it to push attendance logs as they happen."""
    known_device(db, SN, token, x_device_secret)
    db.commit()
    return f"GET OPTION FROM: {SN}\nStamp=9999\nOpStamp=9999\nErrorDelay=60\nDelay=30\nTransTimes=00:00;14:05\nTransInterval=1\nTransFlag=TransData AttLog\nRealtime=1\nEncrypt=0\n"


@router.get("/getrequest", response_class=PlainTextResponse)
def get_request(SN: str = Query(...), token: str = "", x_device_secret: str = Header(default=""), db: Session = Depends(get_db)):
    known_device(db, SN, token, x_device_secret)
    db.commit()
    return "OK"


@router.post("/cdata", response_class=PlainTextResponse)
async def push(request: Request, SN: str = Query(...), table: str = "", token: str = "", x_device_secret: str = Header(default=""),
               db: Session = Depends(get_db)):
    d = known_device(db, SN, token, x_device_secret)
    body = (await request.body()).decode("utf-8", "replace")
    if table.upper() != "ATTLOG":
        db.commit()
        return "OK"
    pins = {e.device_pin: e.id for e in db.scalars(select(Employee).where(Employee.branch_id == d.branch_id, Employee.device_pin != ""))}
    saved = 0
    for line in body.splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 2:
            continue
        pin = parts[0].strip()
        try:
            when = datetime.strptime(parts[1].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=attendance.TZ)
        except ValueError:
            continue  # a line we don't understand is skipped, not fatal
        if db.scalar(select(Punch.id).where(Punch.device_id == d.id, Punch.device_pin == pin, Punch.punched_at == when)):
            continue  # a terminal resends what it has already sent
        db.add(Punch(device_id=d.id, device_pin=pin, employee_id=pins.get(pin), punched_at=when, source="device", branch_id=d.branch_id))
        saved += 1
    db.commit()
    return f"OK:{saved}"
