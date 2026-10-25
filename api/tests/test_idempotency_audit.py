"""Idempotency store/replay and audit_write unit coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.foundation.audit import audit_write
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.idempotency import get_idempotency_key, replay_if_seen, store_response
from app.models import AppLog, IdempotencyKey


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        engine.dispose()


def _request(path="/api/expenses", method="POST", headers=None):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    return Request(scope)


def test_idempotency_store_and_replay(db):
    req = _request(headers={"Idempotency-Key": "abc-123"})
    assert get_idempotency_key(req) == "abc-123"
    assert replay_if_seen(db, key="abc-123", request=req) is None

    store_response(
        db,
        key="abc-123",
        request=req,
        status=201,
        body={"id": 7, "ok": True},
        branch_id=DEFAULT_BRANCH_ID,
        created_by="admin",
    )
    db.commit()

    assert db.query(IdempotencyKey).count() == 1
    replay = replay_if_seen(db, key="abc-123", request=req, branch_id=DEFAULT_BRANCH_ID)
    assert replay is not None
    assert replay.status_code == 201


def test_audit_write_stores_old_new_reason(db):
    user = MagicMock()
    user.id = 1
    user.username = "admin"
    audit_write(
        db,
        user=user,
        action="UPDATE",
        module="expense",
        reference_id=9,
        details="price edit",
        old_value={"amount": 10},
        new_value={"amount": 20},
        reason="correction",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.commit()
    row = db.query(AppLog).first()
    assert row is not None
    assert row.reason == "correction"
    assert "10" in (row.old_value or "")
    assert "20" in (row.new_value or "")
