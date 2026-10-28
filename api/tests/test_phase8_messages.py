import base64
import hashlib
import hmac
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app import messaging
from app.db import SessionLocal, set_actor
from app.models import Branch, Customer, Message
from test_phase3_billing import CASH, ready_repair
from test_phase3_repairs import approved_quote


class Fake:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def send(self, to, body):
        if self.fail:
            raise RuntimeError("Twilio said no")
        self.sent.append((to, body))
        return f"SM{len(self.sent):030d}"


@pytest.fixture
def fake():
    f = Fake()
    messaging._override = f
    yield f
    messaging._override = None


def msgs(admin, status="all"):
    return admin.get(f"/api/messages?status={status}").json()


def issue(admin):
    visit, _, ro = ready_repair(admin)
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    return visit, admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}).json()


def test_events_queue_messages_and_nothing_is_sent_without_a_provider(admin):
    _, inv = issue(admin)
    admin.post(f"/api/invoices/{inv['id']}/payments", json={"amount": "1000", **CASH})
    out = msgs(admin)
    assert out["connected"] is False
    kinds = sorted(m["template"] for m in out["messages"])
    assert kinds == ["car_ready", "invoice_issued", "payment_received", "quotation_sent"]
    assert all(m["status"] == "queued" and m["to"].startswith("+92") for m in out["messages"])
    assert admin.post("/api/messages/send").json() == {"sent": 0, "failed": 0, "waiting": 4}


def test_a_provider_sends_failures_are_kept_and_retry_works(admin, fake):
    _, inv = issue(admin)
    assert {m["status"] for m in msgs(admin)["messages"]} == {"sent"}  # events flush straight away
    assert any("Rs" in body for _, body in fake.sent)
    fake.fail = True
    admin.post(f"/api/invoices/{inv['id']}/payments", json={"amount": "500", **CASH})
    failed = msgs(admin, "failed")["messages"]
    assert len(failed) == 1 and failed[0]["error"] == "Twilio said no" and failed[0]["attempts"] == 1
    fake.fail = False
    assert admin.post(f"/api/messages/{failed[0]['id']}/retry").json()["sent"] == 1
    assert msgs(admin, "failed")["messages"] == []
    assert admin.post(f"/api/messages/{msgs(admin)['messages'][0]['id']}/retry").status_code == 409  # not failed


def test_opted_out_customers_are_never_messaged(admin, fake):
    visit, _, _ = ready_repair(admin)
    admin.put(f"/api/customers/{visit['customer']['id']}", json={**admin.get(f"/api/customers/{visit['customer']['id']}").json(),
                                                                 "whatsapp_opt_out": True})
    before = len(fake.sent)  # the quotation and the ready message went out before the customer opted out
    _, ro = admin.get(f"/api/visits/{visit['id']}").json(), admin.get(f"/api/visits/{visit['id']}").json()["repair_order"]
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]})
    issued = next(m for m in msgs(admin)["messages"] if m["template"] == "invoice_issued")
    assert issued["status"] == "skipped" and "opted out" in issued["error"] and len(fake.sent) == before


def test_wording_can_be_edited_and_switched_off(admin, fake):
    t = admin.get("/api/message-templates").json()
    ready = next(x for x in t["templates"] if x["key"] == "car_ready")
    r = admin.put("/api/message-templates/car_ready", json={"body": "Ready: {car} at {workshop} {oops}", "enabled": True, "version": ready["version"]})
    assert r.status_code == 200
    assert admin.put("/api/message-templates/car_ready", json={"body": "stale", "enabled": True, "version": ready["version"]}).status_code == 409
    admin.put("/api/message-templates/quotation_sent", json={"body": "Quote {number}", "enabled": False,
                                                             "version": next(x for x in t["templates"] if x["key"] == "quotation_sent")["version"]})
    ready_repair(admin)
    bodies = {m["template"]: m["body"] for m in msgs(admin)["messages"]}
    assert "{oops}" in bodies["car_ready"] and "Test Branch" in bodies["car_ready"]  # unknown field is left visible, not a crash
    assert "quotation_sent" not in bodies  # switched off
    assert admin.put("/api/message-templates/nope", json={"body": "hello there", "enabled": True, "version": 1}).status_code == 404


def test_reminders_are_queued_once_and_only_the_latest_step(admin, fake):
    _, inv = issue(admin)
    fake.sent.clear()
    with SessionLocal() as db:
        branch = db.scalar(select(Branch))
        set_actor(db, branch_id=branch.id)
        day = date.today() + timedelta(days=8)  # past +3 and +7, before +15
        assert messaging.run_reminders(db, branch, day)["payment"] == 1
        assert messaging.run_reminders(db, branch, day)["payment"] == 0  # same day again: nothing new
        assert messaging.run_reminders(db, branch, date.today() + timedelta(days=16))["payment"] == 1  # the +15 step
        db.commit()
        keys = sorted(m.dedupe_key.split(":")[-1] for m in db.scalars(select(Message).where(Message.template_key == "payment_reminder")))
    assert keys == ["15", "7"]
    assert admin.put("/api/message-settings", json={"reminder_days": "2,5", "service_reminder_days": 90}).status_code == 200
    assert admin.put("/api/message-settings", json={"reminder_days": "soon", "service_reminder_days": 90}).status_code == 422


def test_welcome_and_service_reminders(admin, fake):
    visit, inv = issue(admin)
    admin.post(f"/api/invoices/{inv['id']}/payments", json={"amount": inv["totals"]["balance"], **CASH})
    admin.post(f"/api/visits/{visit['id']}/gate-pass", json={"odometer_out": 80020, "handed_to": "Owner"})
    out = admin.post("/api/messages/run-reminders").json()["queued"]
    assert out["welcome"] == 1 and out["service"] == 0 and out["payment"] == 0
    with SessionLocal() as db:
        branch = db.scalar(select(Branch))
        set_actor(db, branch_id=branch.id)
        assert messaging.run_reminders(db, branch, date.today() + timedelta(days=181))["service"] == 1
        assert messaging.run_reminders(db, branch, date.today() + timedelta(days=200))["service"] == 0
        db.commit()


def test_phone_numbers_become_international():
    assert messaging.e164("0300-1234567") == "+923001234567"
    assert messaging.e164("+44 7700 900123") == "+447700900123"
    assert messaging.e164("923001234567") == "+923001234567" and messaging.e164("") == ""


# --- webhooks ---------------------------------------------------------------------------------

TOKEN = "test-auth-token"


def sign(url, params):
    payload = url + "".join(k + v for k, v in sorted(params.items()))
    return base64.b64encode(hmac.new(TOKEN.encode(), payload.encode(), hashlib.sha1).digest()).decode()


def hook(admin, path, params, signed=True, sig=None):
    url = "http://testserver" + path
    return admin.post(path, data=params, headers={"X-Twilio-Signature": sig or (sign(url, params) if signed else "")})


def test_webhooks_check_the_signature_update_status_and_honour_stop(admin, fake, monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TOKEN)
    visit, _, _ = ready_repair(admin)
    sid = next(m for m in msgs(admin)["messages"])
    with SessionLocal() as db:
        sid = db.get(Message, sid["id"]).provider_id
    path = "/api/webhooks/twilio/status"
    p = {"MessageSid": sid, "MessageStatus": "delivered"}
    assert hook(admin, path, p, sig="forged").status_code == 403
    assert hook(admin, path, p, signed=False).status_code == 403
    assert hook(admin, path, p).status_code == 204
    assert "delivered" in {m["status"] for m in msgs(admin)["messages"]}
    assert hook(admin, path, {"MessageSid": sid, "MessageStatus": "sent"}).status_code == 204  # late "sent" must not undo "delivered"
    assert "delivered" in {m["status"] for m in msgs(admin)["messages"]}
    assert hook(admin, path, {"MessageSid": sid, "MessageStatus": "undelivered", "ErrorCode": "63016"}).status_code == 204
    assert "failed" in {m["status"] for m in msgs(admin)["messages"]}

    with SessionLocal() as db:
        phone = messaging.e164(db.get(Customer, visit["customer"]["id"]).phone)
    inbound = "/api/webhooks/twilio/inbound"
    assert hook(admin, inbound, {"From": f"whatsapp:{phone}", "Body": "hello"}).status_code == 204
    assert admin.get(f"/api/customers/{visit['customer']['id']}").json()["whatsapp_opt_out"] is False
    assert hook(admin, inbound, {"From": f"whatsapp:{phone}", "Body": " STOP "}).status_code == 204
    assert admin.get(f"/api/customers/{visit['customer']['id']}").json()["whatsapp_opt_out"] is True


def test_webhooks_are_closed_without_credentials(admin, monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    assert admin.post("/api/webhooks/twilio/status", data={"MessageSid": "x"}).status_code == 503
