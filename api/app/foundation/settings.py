"""Workshop settings: configurable thresholds stored as key/value JSON."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

# Keys and defaults (amounts in PKR rupees, not paisa — matches legacy Float columns).
SETTING_DISCOUNT_APPROVAL_PCT = "discount_approval_pct"
SETTING_MANDATORY_RECEIPT_AMOUNT = "mandatory_receipt_amount"
SETTING_COMEBACK_WINDOW_DAYS = "comeback_window_days"
SETTING_PAYMENT_GATE_ENABLED = "payment_gate_enabled"
SETTING_EXPENSE_HEADS = "expense_heads"

DEFAULTS: dict[str, Any] = {
    SETTING_DISCOUNT_APPROVAL_PCT: 10.0,  # % — above this needs manager + reason
    SETTING_MANDATORY_RECEIPT_AMOUNT: 500.0,  # Rs
    SETTING_COMEBACK_WINDOW_DAYS: 14,
    SETTING_PAYMENT_GATE_ENABLED: True,
    SETTING_EXPENSE_HEADS: [
        "Fuel",
        "Utilities",
        "Office supplies",
        "Tools & equipment",
        "Misc",
    ],
}

KNOWN_KEYS = tuple(DEFAULTS.keys())


def _serialize(value: Any) -> str:
    return json.dumps(value, default=str)


def _deserialize(raw: str | None, fallback: Any) -> Any:
    if raw is None or raw == "":
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _scope(branch_id: str | None) -> str:
    """Normalize scope: '' = global workshop defaults."""
    return (branch_id or "").strip()


def get_setting(db: Session, key: str, *, branch_id: str | None = None) -> Any:
    """Return setting value or default. Branch-specific row wins over global."""
    from app.models import AppSetting

    fallback = DEFAULTS.get(key)
    scope = _scope(branch_id)
    q = db.query(AppSetting).filter(AppSetting.key == key)
    if scope:
        row = q.filter(AppSetting.branch_id == scope).first()
        if row is not None:
            return _deserialize(row.value, fallback)
    row = q.filter(AppSetting.branch_id == "").first()
    if row is None:
        return fallback
    return _deserialize(row.value, fallback)


def set_setting(
    db: Session,
    key: str,
    value: Any,
    *,
    branch_id: str | None = None,
    updated_by: str | None = None,
    flush: bool = True,
) -> Any:
    from app.models import AppSetting

    if key not in DEFAULTS:
        raise ValueError(f"unknown setting key: {key}")
    scope = _scope(branch_id)
    row = (
        db.query(AppSetting)
        .filter(AppSetting.key == key, AppSetting.branch_id == scope)
        .first()
    )
    if row is None:
        row = AppSetting(key=key, branch_id=scope)
        db.add(row)
    row.value = _serialize(value)
    row.updated_by = updated_by
    if flush:
        db.flush()
    return value


def get_workshop_settings(db: Session, *, branch_id: str | None = None) -> dict[str, Any]:
    return {key: get_setting(db, key, branch_id=branch_id) for key in KNOWN_KEYS}


def ensure_default_settings(db: Session) -> None:
    """Seed missing global settings rows (additive, safe to re-run)."""
    from app.models import AppSetting

    existing = {
        row.key
        for row in db.query(AppSetting).filter(AppSetting.branch_id == "").all()
    }
    for key, value in DEFAULTS.items():
        if key in existing:
            continue
        db.add(AppSetting(key=key, value=_serialize(value), branch_id=""))
    db.flush()


def discount_needs_approval(db: Session, discount_pct: float, *, branch_id: str | None = None) -> bool:
    threshold = float(get_setting(db, SETTING_DISCOUNT_APPROVAL_PCT, branch_id=branch_id) or 0)
    return float(discount_pct or 0) > threshold


def receipt_required(db: Session, amount: float, *, branch_id: str | None = None) -> bool:
    floor = float(get_setting(db, SETTING_MANDATORY_RECEIPT_AMOUNT, branch_id=branch_id) or 0)
    return float(amount or 0) >= floor


def payment_gate_enabled(db: Session, *, branch_id: str | None = None) -> bool:
    return bool(get_setting(db, SETTING_PAYMENT_GATE_ENABLED, branch_id=branch_id))


def comeback_window_days(db: Session, *, branch_id: str | None = None) -> int:
    return int(get_setting(db, SETTING_COMEBACK_WINDOW_DAYS, branch_id=branch_id) or 14)


def expense_heads(db: Session, *, branch_id: str | None = None) -> list[str]:
    raw = get_setting(db, SETTING_EXPENSE_HEADS, branch_id=branch_id)
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return list(DEFAULTS[SETTING_EXPENSE_HEADS])
