"""Customer messages: the queue, the wording, the reminder days, and Twilio's callbacks."""

import os
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import messaging
from app.auth import Actor, current_actor, require
from app.db import get_db, set_actor
from app.models import Customer, Message, MessageTemplate
from app.validators import Text

router = APIRouter(prefix="/api", tags=["messages"])
can_message = require("messages")


def _out(m: Message, names: dict) -> dict:
    return {"id": m.id, "customer_id": m.customer_id, "customer": names.get(m.customer_id, ""), "to": m.to_phone, "template": m.template_key,
            "body": m.body, "status": m.status, "error": m.error, "attempts": m.attempts, "created_at": m.created_at, "sent_at": m.sent_at}


@router.get("/messages")
def list_messages(status: Literal["all", "queued", "sent", "delivered", "read", "failed", "skipped"] = "all", limit: int = 100,
                  actor: Actor = Depends(can_message), db: Session = Depends(get_db)):
    stmt = select(Message).where(Message.branch_id == actor.branch.id)
    if status != "all":
        stmt = stmt.where(Message.status == status)
    rows = list(db.scalars(stmt.order_by(Message.created_at.desc()).limit(min(limit, 300))))
    names = {c.id: c.name for c in db.scalars(select(Customer).where(Customer.id.in_({m.customer_id for m in rows if m.customer_id})))}
    counts = dict(db.execute(select(Message.status, func.count()).where(Message.branch_id == actor.branch.id).group_by(Message.status)).all())
    return {"connected": messaging.connected(), "counts": counts, "messages": [_out(m, names) for m in rows]}


@router.post("/messages/send")
def send_queued(actor: Actor = Depends(can_message), db: Session = Depends(get_db)):
    return messaging.dispatch(db, actor.branch.id)


@router.post("/messages/{message_id}/retry")
def retry(message_id: uuid.UUID, actor: Actor = Depends(can_message), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or m.branch_id != actor.branch.id:
        raise HTTPException(404, "Message not found")
    if m.status != "failed":
        raise HTTPException(409, "Only a failed message can be retried")
    m.status, m.error = "queued", ""
    db.commit()
    return messaging.dispatch(db, actor.branch.id)


@router.post("/messages/run-reminders")
def run_reminders(actor: Actor = Depends(can_message), db: Session = Depends(get_db)):
    """Queues the reminders that are due, once each. Safe to run again; a daily schedule can call it."""
    made = messaging.run_reminders(db, actor.branch)
    db.commit()
    return {"queued": made, **messaging.dispatch(db, actor.branch.id)}


# --- wording and settings --------------------------------------------------------------------

@router.get("/message-templates")
def templates(actor: Actor = Depends(can_message), db: Session = Depends(get_db)):
    have = messaging.ensure_templates(db, actor.branch)
    db.commit()
    return {"templates": [{"key": k, "label": messaging.DEFAULTS[k][0], "body": t.body, "enabled": t.enabled, "version": t.version}
                          for k, t in have.items()],
            "fields": ["name", "number", "total", "balance", "car", "workshop", "days"],
            "reminder_days": actor.branch.reminder_days, "service_reminder_days": actor.branch.service_reminder_days}


class TemplateIn(BaseModel):
    body: Text = Field(min_length=5, max_length=600)
    enabled: bool
    version: int


@router.put("/message-templates/{key}")
def save_template(key: str, body: TemplateIn, actor: Actor = Depends(can_message), db: Session = Depends(get_db)):
    t = messaging.ensure_templates(db, actor.branch).get(key)
    if not t:
        raise HTTPException(404, "No such message")
    if body.version != t.version:
        raise HTTPException(409, "This message was changed on another device. Reload to continue.")
    t.body, t.enabled = body.body, body.enabled
    db.commit()
    return {"key": key, "body": t.body, "enabled": t.enabled, "version": t.version}


class ReminderIn(BaseModel):
    reminder_days: str = Field(pattern=r"^\d{1,3}(,\d{1,3}){0,5}$", description="e.g. 3,7,15")
    service_reminder_days: int = Field(ge=30, le=730)


@router.put("/message-settings")
def save_settings(body: ReminderIn, actor: Actor = Depends(can_message), db: Session = Depends(get_db)):
    actor.branch.reminder_days, actor.branch.service_reminder_days = body.reminder_days, body.service_reminder_days
    db.commit()
    return {"reminder_days": body.reminder_days, "service_reminder_days": body.service_reminder_days}


# --- Twilio callbacks (no login: the signature is the credential) -----------------------------

async def _verified(request: Request) -> dict:
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not token:
        raise HTTPException(503, "Messaging is not set up")
    form = {k: str(v) for k, v in (await request.form()).items()}
    base = os.environ.get("PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    if not messaging.valid_signature(token, base + request.url.path, form, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(403, "Bad signature")
    return form


@router.post("/webhooks/twilio/status")
async def twilio_status(request: Request, db: Session = Depends(get_db)):
    form = await _verified(request)
    m = db.scalar(select(Message).where(Message.provider_id == form.get("MessageSid", "")))
    if m:
        set_actor(db, branch_id=m.branch_id)
        messaging.apply_status(m, form.get("MessageStatus", ""), form.get("ErrorMessage") or form.get("ErrorCode", ""))
        db.commit()
    return Response(status_code=204)


@router.post("/webhooks/twilio/inbound")
async def twilio_inbound(request: Request, db: Session = Depends(get_db)):
    """A customer replied. STOP (and its synonyms) turns WhatsApp messages off for that number."""
    form = await _verified(request)
    if form.get("Body", "").strip().lower() in messaging.STOP_WORDS:
        messaging.opt_out_phone(db, form.get("From", "").removeprefix("whatsapp:"))
        db.commit()
    return Response(status_code=204)
