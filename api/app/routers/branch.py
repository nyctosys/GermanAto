"""The current branch's settings, and the audit log."""

import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import Actor, current_actor, require
from app.db import get_db
from app.models import AuditLog, Branch, User
from app.validators import Email, Name, Phone, Text

router = APIRouter(prefix="/api", tags=["branch"])


class BranchOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    address: str
    phone: str
    email: str
    tax_rate: Decimal
    timezone: str
    currency: str
    version: int


class BranchUpdate(BaseModel):
    name: Name
    address: Text = Field(default="", max_length=300)
    phone: Phone = ""
    email: Email | None = None
    tax_rate: Decimal = Field(ge=0, le=100, decimal_places=2)
    timezone: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    version: int  # the version the form was loaded with

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, v: str) -> str:
        if v not in available_timezones():
            raise ValueError("Unknown timezone")
        return v


@router.get("/branch", response_model=BranchOut)
def get_branch(actor: Actor = Depends(current_actor)):
    return BranchOut.model_validate(actor.branch, from_attributes=True)


@router.put("/branch", response_model=BranchOut)
def update_branch(body: BranchUpdate, actor: Actor = Depends(require("settings")), db: Session = Depends(get_db)):
    branch = db.get(Branch, actor.branch.id)
    if body.version != branch.version:
        raise HTTPException(409, "Someone else changed these settings. Reload and try again.")
    for key, value in body.model_dump(exclude={"version"}).items():
        setattr(branch, key, value if value is not None else "")
    db.commit()
    return BranchOut.model_validate(branch, from_attributes=True)


@router.get("/audit")
def audit_log(
    actor: Actor = Depends(require("audit")),
    db: Session = Depends(get_db),
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    before: datetime | None = Query(None, description="Return entries older than this (for paging)"),
    limit: int = Query(50, ge=1, le=200),
):
    q = (select(AuditLog, User.username).outerjoin(User, User.id == AuditLog.user_id)
         # Branch-less entries (failed sign-ins, first-run setup) happen before
         # anyone is in a branch; they are shown to every branch's auditors.
         .where(or_(AuditLog.branch_id == actor.branch.id, AuditLog.branch_id.is_(None)))
         .order_by(AuditLog.at.desc()).limit(limit))
    for column, value in ((AuditLog.entity_type, entity_type), (AuditLog.entity_id, entity_id),
                          (AuditLog.user_id, user_id), (AuditLog.action, action)):
        if value is not None:
            q = q.where(column == value)
    if before:
        q = q.where(AuditLog.at < before)
    return [
        {"id": a.id, "at": a.at, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
         "changes": a.changes, "user": username, "ip": a.ip}
        for a, username in db.execute(q)
    ]
