from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.models import AuditLog, SyncOutbox
from conftest import login

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def make_user(admin, username="acct", role="Accountant", password="acct-pass-123", **extra):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    body = {"username": username, "full_name": "Test User", "password": password, "role_id": roles[role],
            "branch_ids": [branch_id], **extra}
    r = admin.post("/api/users", json=body)
    assert r.status_code == 201, r.json()
    return r.json()


def signed_in(username, password) -> TestClient:
    client = TestClient(app)
    assert login(client, username, password).status_code == 200
    return client


# --- auth -----------------------------------------------------------------

def test_requires_sign_in(anon):
    assert anon.get("/api/auth/me").status_code == 401
    assert anon.get("/api/users").status_code == 401


def test_login_sets_httponly_cookie_and_me_lists_permissions(anon):
    r = login(anon, "  OWNER ", "admin-pass-123")  # username is case- and space-insensitive
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    me = anon.get("/api/auth/me").json()
    assert me["user"]["username"] == "owner" and me["role"]["is_admin"]
    assert {"users", "settings", "audit", "attachments"} <= set(me["permissions"])
    assert me["branch"]["code"] == "A1F3"


def test_wrong_password_then_lockout(anon):
    for _ in range(5):
        assert login(anon, "owner", "nope-nope").status_code == 401
    assert login(anon, "owner", "admin-pass-123").status_code == 423
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).where(AuditLog.action == "login_failed")) == 5


def test_failed_sign_ins_show_in_audit_log(admin):
    login(TestClient(app), "owner", "nope-nope")
    assert admin.get("/api/audit", params={"action": "login_failed"}).json()[0]["changes"] == {"username": "owner"}


def test_logout_ends_session(admin):
    assert admin.post("/api/auth/logout").status_code == 200
    assert admin.get("/api/auth/me").status_code == 401


# --- users & roles --------------------------------------------------------

def test_permissions_are_enforced(admin):
    make_user(admin)
    acct = signed_in("acct", "acct-pass-123")
    assert acct.get("/api/users").status_code == 403          # no "users"
    assert acct.get("/api/audit").status_code == 200          # Accountant has "audit"
    assert acct.put("/api/branch", json={}).status_code in (403, 422)


def test_user_input_is_normalised_and_validated(admin):
    u = make_user(admin, username="Front.Desk", phone="0300-1234567", email=" Desk@Example.com ")
    assert (u["username"], u["phone"], u["email"]) == ("front.desk", "+923001234567", "desk@example.com")
    r = admin.post("/api/users", json={"username": "x", "full_name": "", "password": "short",
                                       "role_id": u["role_id"], "branch_ids": []})
    assert r.status_code == 422
    assert admin.post("/api/users", json={**{k: u[k] for k in ("role_id", "branch_ids")}, "username": "front.desk",
                                          "full_name": "Dup", "password": "long-enough"}).status_code == 409


def test_cannot_disable_self(admin):
    me = admin.get("/api/auth/me").json()
    assert admin.patch(f"/api/users/{me['user']['id']}", json={"is_active": False}).status_code == 409


def test_disabled_user_cannot_sign_in_and_reset_unlocks(admin):
    u = make_user(admin)
    admin.patch(f"/api/users/{u['id']}", json={"is_active": False})
    assert login(TestClient(app), "acct", "acct-pass-123").status_code == 401
    admin.patch(f"/api/users/{u['id']}", json={"is_active": True, "password": "new-pass-456"})
    assert login(TestClient(app), "acct", "new-pass-456").status_code == 200


def test_unknown_permission_rejected(admin):
    assert admin.post("/api/roles", json={"name": "Weird", "permissions": ["launch-rockets"]}).status_code == 422
    r = admin.post("/api/roles", json={"name": "Shop assistant", "permissions": ["attachments", "dashboard"]})
    assert r.status_code == 201 and r.json()["permissions"] == ["attachments", "dashboard"]


# --- branch settings & audit ---------------------------------------------

def test_branch_update_validates_and_detects_stale_edits(admin):
    b = admin.get("/api/branch").json()
    body = {**b, "phone": "042 35761234", "tax_rate": "18.00"}
    body.pop("id"), body.pop("code")
    assert admin.put("/api/branch", json={**body, "tax_rate": "101"}).status_code == 422
    assert admin.put("/api/branch", json={**body, "timezone": "Mars/Base"}).status_code == 422
    r = admin.put("/api/branch", json=body)
    assert r.status_code == 200 and r.json()["phone"] == "+924235761234"
    assert admin.put("/api/branch", json=body).status_code == 409  # same old version again


def test_audit_records_only_what_changed(admin):
    b = admin.get("/api/branch").json()
    body = {k: v for k, v in b.items() if k not in ("id", "code")}
    admin.put("/api/branch", json={**body, "name": "Renamed"})
    entries = admin.get("/api/audit", params={"entity_type": "branches", "action": "update"}).json()
    assert entries[0]["changes"] == {"name": ["Test Branch", "Renamed"]}
    assert entries[0]["user"] == "owner"


def test_every_change_lands_in_the_outbox(admin):
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(SyncOutbox))
    make_user(admin)
    with SessionLocal() as db:
        tables = set(db.scalars(select(SyncOutbox.table_name).offset(before)))
    assert {"users", "user_branches"} <= tables


# --- attachments ----------------------------------------------------------

def test_attachment_upload_sniffs_type_and_serves_file(admin):
    r = admin.post("/api/attachments", files={"file": ("receipt.png", PNG, "image/png")},
                   data={"entity_type": "expenses", "note": "fuel"})
    assert r.status_code == 201, r.json()
    att = r.json()
    assert att["mime"] == "image/png"
    got = admin.get(att["url"])
    assert got.status_code == 200 and got.content == PNG
    assert got.headers["x-content-type-options"] == "nosniff"


def test_attachment_rejects_disguised_files(admin):
    r = admin.post("/api/attachments", files={"file": ("receipt.png", b"MZ\x90\x00 not an image", "image/png")})
    assert r.status_code == 415
    assert admin.post("/api/attachments", files={"file": ("empty.pdf", b"", "application/pdf")}).status_code == 422
