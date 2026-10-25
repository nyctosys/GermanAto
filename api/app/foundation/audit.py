"""Structured audit writes: who / what / old / new / reason."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session


def _serialize(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except TypeError:
        return json.dumps(str(value))


def audit_write(
    db: Session,
    *,
    user,
    action: str,
    module: str,
    reference_id: int | None,
    details: str = "",
    old_value: Any = None,
    new_value: Any = None,
    reason: str | None = None,
    branch_id: str | None = None,
    request: Request | None = None,
    flush: bool = True,
) -> None:
    """Persist an AppLog row with optional old/new/reason. Never raises to callers.

    Set flush=False when called from a before_flush hook (nested flush is unsafe).
    """
    try:
        from app.models import AppLog
        from app.foundation.branch import DEFAULT_BRANCH_ID

        ip_address = None
        if request is not None:
            ip_address = request.headers.get("X-Forwarded-For") or (
                request.client.host if request.client else None
            )
            if ip_address and "," in ip_address:
                ip_address = ip_address.split(",")[0].strip()

        entry = AppLog(
            user_id=user.id if user else None,
            username=user.username if user else "anonymous/system",
            action=action,
            module=module,
            reference_id=reference_id,
            details=details or "",
            ip_address=ip_address,
            old_value=_serialize(old_value),
            new_value=_serialize(new_value),
            reason=reason,
            branch_id=branch_id or DEFAULT_BRANCH_ID,
        )
        db.add(entry)
        if flush:
            db.flush()
    except Exception:
        # Audit must not break business writes
        import logging

        logging.getLogger(__name__).exception("audit_write failed")
