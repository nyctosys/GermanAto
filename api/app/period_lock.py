"""Month-end close for financial records."""
from __future__ import annotations

from datetime import date
from functools import wraps
from typing import Any, Callable, Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models import FinancialPeriod


def _period_of(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return None
    return value.year, value.month


def is_period_open(db: Session, when) -> bool:
    period = _period_of(when)
    if not period:
        return True

    year, month = period
    today = date.today()
    default_open = (year, month) >= (today.year, today.month)

    override = db.query(FinancialPeriod).filter_by(year=year, month=month).first()
    return override.is_open if override else default_open


def period_label(when) -> str:
    period = _period_of(when)
    return f"{period[0]}-{period[1]:02d}" if period else "that period"


def check_period_editable(db: Session, when, user) -> None:
    """Raise HTTPException if this date sits in a closed month. Admins pass."""
    if user is not None and getattr(user, "role", None) == "admin":
        return
    if is_period_open(db, when):
        return
    raise HTTPException(
        status_code=403,
        detail={
            "error": (
                f"{period_label(when)} is closed. Records from a finished month "
                f"cannot be changed - ask an admin if this needs a correction."
            ),
            "period": period_label(when),
            "closed": True,
        },
    )


def body_date(field: str = "date"):
    def getter(body: dict | None = None, **kwargs):
        data = body or {}
        return data.get(field)

    return getter


def record_date(model, pk_kwarg, field: str = "date"):
    def getter(db: Session = None, **kwargs):
        pk = kwargs.get(pk_kwarg)
        row = db.get(model, pk) if db is not None and pk is not None else None
        return getattr(row, field, None) if row else None

    return getter


def guard_period(get_date: Callable):
    """Decorator for financial write routes (FastAPI sync endpoints)."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = kwargs.get("current_user")
            db = kwargs.get("db")
            try:
                when = get_date(*args, **kwargs)
            except Exception:
                when = None
            if db is not None:
                check_period_editable(db, when, user)
            return f(*args, **kwargs)

        return wrapper

    return decorator


def guard_both(model, pk_kwarg, field: str = "date"):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = kwargs.get("current_user")
            db = kwargs.get("db")
            existing = record_date(model, pk_kwarg, field)(**kwargs)
            if db is not None:
                check_period_editable(db, existing, user)
            body = kwargs.get("body") or {}
            incoming = body.get(field) if isinstance(body, dict) else None
            if incoming and db is not None:
                check_period_editable(db, incoming, user)
            return f(*args, **kwargs)

        return wrapper

    return decorator
