"""Smoke/contract tests for the HTTP API.

Runs on in-memory SQLite by default. Point DATABASE_URL at a throwaway MySQL
database to run against MySQL instead (tables are dropped and recreated).

Response shapes are frozen in tests/contracts/*.json; the FastAPI port must
produce the same shapes. Regenerate after an intentional change with
UPDATE_CONTRACTS=1 pytest.
"""
import json
import os
import sys
from pathlib import Path

import pytest
import werkzeug

# Flask 2.2's test client reads werkzeug.__version__, which Werkzeug 3 removed
# (same shim as test_permissions_matrix.py).
werkzeug.__version__ = getattr(werkzeug, "__version__", "3")

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["SECRET_KEY"] = "test-secret"
# Empty values stop load_dotenv() pulling real Twilio credentials from .env,
# which keeps WhatsApp sending disabled.
for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_NUMBER"):
    os.environ[key] = ""

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app as flask_app  # noqa: E402
from models import User, db  # noqa: E402

CONTRACTS = Path(__file__).parent / "contracts"


def body(response):
    """JSON body for both Flask's test client and Starlette's TestClient."""
    j = response.json
    return j() if callable(j) else j


def shape(value):
    """Reduce JSON to its structure: keys and value types, lists by first element."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"  # Python can't tell 5.0 from 5 once it's JSON
    if value is None:
        return "null"
    return "str"


@pytest.fixture
def contract():
    def check(name, response):
        actual = shape(body(response))
        path = CONTRACTS / f"{name}.json"
        if os.getenv("UPDATE_CONTRACTS") or not path.exists():
            CONTRACTS.mkdir(exist_ok=True)
            path.write_text(json.dumps(actual, indent=2) + "\n")
            return
        assert actual == json.loads(path.read_text()), f"response shape changed: {path.name}"
    return check


@pytest.fixture
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        for username, role in (("admin", "admin"), ("acct", "accountant"), ("inv", "inventory_manager")):
            user = User(username=username, email=f"{username}@example.com", role=role)
            user.set_password("pw")
            db.session.add(user)
        db.session.commit()
    yield flask_app.test_client()
    with flask_app.app_context():
        db.session.remove()


def login(client, username):
    r = client.post("/api/auth/login", json={"username": username, "password": "pw"})
    assert r.status_code == 200, body(r)
    return {"Authorization": f"Bearer {body(r)['access_token']}"}


@pytest.fixture
def admin(client):
    return login(client, "admin")
