"""Customer messages over WhatsApp. Events and reminders only *queue* a message; sending is a
separate step so a slow or missing provider never blocks the counter. With no Twilio credentials
in the environment nothing is sent: messages wait in the queue (dry run)."""

import base64
import hashlib
import hmac
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Branch, Car, Customer, Invoice, Message, MessageTemplate, Visit

# key -> (what it is for, default wording). Fields: {name} {number} {total} {balance} {car} {workshop} {days}
DEFAULTS: dict[str, tuple[str, str]] = {
    "quotation_sent": ("Quotation sent", "Hello {name}, your quotation {number} from {workshop} is ready: {total}. Reply to approve it."),
    "car_ready": ("Car ready", "Hello {name}, your {car} is ready for collection at {workshop}."),
    "invoice_issued": ("Invoice issued", "Hello {name}, invoice {number} from {workshop}: total {total}, balance {balance}. Thank you."),
    "payment_received": ("Payment received", "Hello {name}, we received your payment for {number}. Balance now {balance}. Thank you."),
    "payment_reminder": ("Payment reminder", "Hello {name}, a friendly reminder: invoice {number} has {balance} unpaid ({days} days). {workshop}"),
    "service_reminder": ("Service reminder", "Hello {name}, it has been {days} days since we serviced your {car}. Book your next service with {workshop}."),
    "welcome": ("Welcome", "Welcome to {workshop}, {name}. Thank you for trusting us with your {car}. We will keep you updated here."),
}
STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}


def ensure_templates(db: Session, branch: Branch) -> dict[str, MessageTemplate]:
    have = {t.key: t for t in db.scalars(select(MessageTemplate).where(MessageTemplate.branch_id == branch.id))}
    for key, (_, body) in DEFAULTS.items():
        if key not in have:
            have[key] = MessageTemplate(branch_id=branch.id, key=key, body=body)
            db.add(have[key])
    db.flush()
    return have


def e164(phone: str) -> str:
    """03001234567 -> +923001234567 (Pakistan); anything already international keeps its country code."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if phone.strip().startswith("+") or phone.strip().startswith("00"):
        return "+" + digits.removeprefix("00")
    if digits.startswith("0"):
        return "+92" + digits[1:]
    return "+" + digits if digits.startswith("92") else "+92" + digits


def fmt_money(v: Decimal) -> str:
    return f"Rs {v:,.0f}"


class _Fields(dict):
    def __missing__(self, key):  # a typo in a template shows as {key} instead of crashing the sale
        return "{" + key + "}"


def render(body: str, ctx: dict) -> str:
    return body.format_map(_Fields(ctx))


def queue(db: Session, branch: Branch, customer: Customer | None, key: str, ctx: dict, dedupe: str | None = None) -> Message | None:
    """Queues one message unless the template is off, it was queued before, or the customer cannot be messaged."""
    tpl = ensure_templates(db, branch)[key]
    if not tpl.enabled:
        return None
    if dedupe and db.scalar(select(Message.id).where(Message.dedupe_key == dedupe)):
        return None
    ctx = {"workshop": branch.name, "name": customer.name if customer else "", **ctx}
    msg = Message(branch_id=branch.id, customer_id=customer.id if customer else None, template_key=key,
                  to_phone=e164(customer.phone) if customer else "", body=render(tpl.body, ctx), dedupe_key=dedupe)
    if not customer or not msg.to_phone:
        msg.status, msg.error = "skipped", "No phone number"
    elif customer.whatsapp_opt_out:
        msg.status, msg.error = "skipped", "The customer has opted out of WhatsApp messages"
    db.add(msg)
    db.flush()
    return msg


# --- sending ---------------------------------------------------------------------------------

class Provider(Protocol):
    def send(self, to: str, body: str) -> str: ...  # returns the provider's message id; raises on failure


class Twilio:
    def __init__(self, sid: str, token: str, sender: str):
        self.sid, self.token, self.sender = sid, token, sender

    def send(self, to: str, body: str) -> str:
        data = urllib.parse.urlencode({"To": f"whatsapp:{to}", "From": f"whatsapp:{self.sender}", "Body": body}).encode()
        req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json", data=data)
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{self.sid}:{self.token}".encode()).decode())
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)["sid"]


_override: Provider | None = None  # tests plug a fake in here


def provider() -> Provider | None:
    if _override:
        return _override
    sid, token, sender = (os.environ.get(k, "") for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM"))
    return Twilio(sid, token, sender) if sid and token and sender else None


def connected() -> bool:
    return provider() is not None


def dispatch(db: Session, branch_id, limit: int = 50) -> dict:
    """Sends what is queued. No provider: leaves everything queued."""
    p = provider()
    rows = list(db.scalars(select(Message).where(Message.branch_id == branch_id, Message.status == "queued")
                           .order_by(Message.created_at).limit(limit).with_for_update(skip_locked=True)))
    if not p:
        return {"sent": 0, "failed": 0, "waiting": len(rows)}
    sent = failed = 0
    for m in rows:
        m.attempts += 1
        try:
            m.provider_id, m.status, m.sent_at, m.error = p.send(m.to_phone, m.body), "sent", utcnow(), ""
            sent += 1
        except Exception as e:  # noqa: BLE001  any provider failure is recorded on the message, never raised into a sale
            m.status, m.error = "failed", str(e)[:300]
            failed += 1
    db.commit()
    return {"sent": sent, "failed": failed, "waiting": 0}


def flush(db: Session, branch_id) -> None:
    """Best-effort send right after an event; the queue and the retry button cover any failure."""
    try:
        dispatch(db, branch_id)
    except Exception:  # noqa: BLE001
        db.rollback()


# --- webhooks --------------------------------------------------------------------------------

def valid_signature(token: str, url: str, params: dict, signature: str) -> bool:
    """Twilio signs the full URL plus every POST field (sorted by name) with the account's auth token."""
    payload = url + "".join(k + str(v) for k, v in sorted(params.items()))
    digest = base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(digest, signature or "")


STATUS_ORDER = {"queued": 0, "sent": 1, "delivered": 2, "read": 3}


def apply_status(m: Message, twilio_status: str, error: str = "") -> None:
    new = {"queued": "queued", "accepted": "queued", "sending": "queued", "sent": "sent", "delivered": "delivered", "read": "read",
           "failed": "failed", "undelivered": "failed"}.get(twilio_status)
    if not new:
        return
    if new == "failed":
        m.status, m.error = "failed", error or "The provider could not deliver it"
    elif STATUS_ORDER.get(new, 0) > STATUS_ORDER.get(m.status, -1):  # webhooks arrive out of order; never go backwards
        m.status = new


def opt_out_phone(db: Session, phone: str) -> int:
    n = 0
    for c in db.scalars(select(Customer).where(Customer.whatsapp_opt_out.is_(False))):
        if e164(c.phone) == phone or e164(c.phone_alt) == phone:
            c.whatsapp_opt_out = True
            n += 1
    return n


# --- reminders -------------------------------------------------------------------------------

def due_days(branch: Branch) -> list[int]:
    return sorted({int(x) for x in re.findall(r"\d+", branch.reminder_days or "") if 0 < int(x) <= 365})


def run_reminders(db: Session, branch: Branch, today: date | None = None) -> dict:
    """Queues every reminder that is due and not queued before (the dedupe key makes it safe to run daily or twice)."""
    from app.routers.billing import balance_of  # late: billing imports this module for its events
    today = today or date.today()
    made = {"payment": 0, "service": 0, "welcome": 0}
    days = due_days(branch)
    for inv in db.scalars(select(Invoice).where(Invoice.branch_id == branch.id, Invoice.status == "issued", Invoice.customer_id.is_not(None))):
        age = (today - inv.issued_at.date()).days
        step = max((d for d in days if d <= age), default=None)  # only the latest step, never a burst of three
        bal = balance_of(db, inv)["balance"]
        if step is None or bal <= 0:
            continue
        c = db.get(Customer, inv.customer_id)
        if queue(db, branch, c, "payment_reminder", {"number": inv.number, "balance": fmt_money(bal), "days": age}, f"pay:{inv.id}:{step}"):
            made["payment"] += 1
    closed = select(Visit.customer_id, func.max(Visit.closed_at), func.count()).where(
        Visit.branch_id == branch.id, Visit.status == "closed").group_by(Visit.customer_id)
    for cid, last, count in db.execute(closed):
        c = db.get(Customer, cid)
        v = db.scalar(select(Visit).where(Visit.customer_id == cid, Visit.status == "closed").order_by(Visit.closed_at.desc()))
        k = db.get(Car, v.car_id)
        car = f"{k.make} {k.model}".strip() if k else "car"
        if count == 1 and queue(db, branch, c, "welcome", {"car": car}, f"welcome:{cid}"):
            made["welcome"] += 1
        still_open = db.scalar(select(Visit.id).where(Visit.customer_id == cid, Visit.status == "open"))
        age = (today - last.date()).days
        if not still_open and age >= branch.service_reminder_days and queue(
                db, branch, c, "service_reminder", {"car": car, "days": age}, f"service:{cid}:{v.id}"):
            made["service"] += 1
    return made
