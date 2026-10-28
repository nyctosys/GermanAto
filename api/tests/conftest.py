"""Tests run against a real Postgres (constraints and JSONB are part of what
is being tested). Point TEST_DATABASE_URL at a throwaway database: every
test starts from empty tables."""

import os
import tempfile

import pytest

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL",
                                            "postgresql+psycopg://postgres@127.0.0.1:5432/germanato_test")
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="germanato-files-")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

ADMIN_PASSWORD = "admin-pass-123"


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def clean(schema):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE " + ", ".join(t.name for t in Base.metadata.sorted_tables) + " CASCADE"))
    seed("Test Branch", "owner", ADMIN_PASSWORD, branch_code="A1F3")


def login(client: TestClient, username: str, password: str):
    return client.post("/api/auth/login", json={"username": username, "password": password})


@pytest.fixture
def admin() -> TestClient:
    client = TestClient(app)
    assert login(client, "owner", ADMIN_PASSWORD).status_code == 200
    return client


@pytest.fixture
def anon() -> TestClient:
    return TestClient(app)
