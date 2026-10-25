"""Workshop settings, granular permissions, and override reason guards."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.foundation.overrides import (
    assert_discount_override,
    assert_payment_gate_override,
    require_audit_reason,
    require_override,
    user_has_permission,
)
from app.foundation.roles import GRANULAR_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS
from app.foundation.settings import (
    DEFAULTS,
    SETTING_DISCOUNT_APPROVAL_PCT,
    SETTING_PAYMENT_GATE_ENABLED,
    ensure_default_settings,
    get_setting,
    get_workshop_settings,
    set_setting,
)


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


def _user(role: str = "manager", username: str = "mgr"):
    u = MagicMock()
    u.id = 1
    u.username = username
    u.role = role
    return u


def test_ensure_default_settings(db):
    ensure_default_settings(db)
    db.commit()
    settings = get_workshop_settings(db)
    assert settings[SETTING_DISCOUNT_APPROVAL_PCT] == DEFAULTS[SETTING_DISCOUNT_APPROVAL_PCT]
    assert settings["mandatory_receipt_amount"] == 500.0
    assert settings["comeback_window_days"] == 14
    assert settings["payment_gate_enabled"] is True
    assert isinstance(settings["expense_heads"], list)
    assert len(settings["expense_heads"]) >= 1


def test_set_and_get_setting(db):
    ensure_default_settings(db)
    set_setting(db, SETTING_DISCOUNT_APPROVAL_PCT, 15.0, updated_by="admin")
    db.commit()
    assert get_setting(db, SETTING_DISCOUNT_APPROVAL_PCT) == 15.0


def test_granular_permissions_in_role_map():
    for perm in GRANULAR_PERMISSIONS:
        assert perm in DEFAULT_ROLE_PERMISSIONS["admin"]
        assert perm in DEFAULT_ROLE_PERMISSIONS["owner"]
        assert perm in DEFAULT_ROLE_PERMISSIONS["manager"]


def test_store_keeper_has_adjust_stock():
    assert "adjust_stock" in DEFAULT_ROLE_PERMISSIONS["store_keeper"]
    assert "reopen_period" not in DEFAULT_ROLE_PERMISSIONS["store_keeper"]


def test_user_has_permission_defaults(db):
    ensure_default_settings(db)
    assert user_has_permission(db, _user("manager"), "approve_discount")
    assert user_has_permission(db, _user("technician"), "qc_signoff")
    assert not user_has_permission(db, _user("technician"), "reopen_period")
    assert user_has_permission(db, _user("admin"), "reopen_period")


def test_require_audit_reason_missing():
    with pytest.raises(HTTPException) as ei:
        require_audit_reason(kind="delete", reason="")
    assert ei.value.status_code == 400
    assert ei.value.detail["require_reason"] is True


def test_require_override_period_reopen(db):
    with pytest.raises(HTTPException) as ei:
        require_override(db, _user("manager"), "period_reopen", reason="")
    assert ei.value.status_code == 400

    text = require_override(db, _user("manager"), "period_reopen", reason="month error")
    assert text == "month error"

    with pytest.raises(HTTPException) as ei2:
        require_override(db, _user("technician"), "period_reopen", reason="oops")
    assert ei2.value.status_code == 403


def test_discount_override_threshold(db):
    ensure_default_settings(db)
    set_setting(db, SETTING_DISCOUNT_APPROVAL_PCT, 10.0)
    db.commit()
    # Below threshold — no reason needed
    assert assert_discount_override(db, _user("accountant"), 5.0) is None
    # Above — needs reason + permission
    with pytest.raises(HTTPException):
        assert_discount_override(db, _user("accountant"), 25.0, reason="")
    assert (
        assert_discount_override(db, _user("accountant"), 25.0, reason="loyal customer")
        == "loyal customer"
    )


def test_payment_gate_override(db):
    ensure_default_settings(db)
    set_setting(db, SETTING_PAYMENT_GATE_ENABLED, True)
    db.commit()
    assert assert_payment_gate_override(db, _user("manager"), bypass=False) is None
    with pytest.raises(HTTPException):
        assert_payment_gate_override(db, _user("manager"), bypass=True, reason="")
    assert (
        assert_payment_gate_override(
            db, _user("manager"), bypass=True, reason="manager waiver"
        )
        == "manager waiver"
    )
