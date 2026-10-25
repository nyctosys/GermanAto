"""Admin API for financial period open/close."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.log_utils import log_action
from app.models import FinancialPeriod
from app.period_lock import is_period_open

router = APIRouter()


def _json(data, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/financial-periods")
def list_periods(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """The last 13 months and whether each is still editable."""
    today = date.today()
    overrides = {(p.year, p.month): p for p in db.query(FinancialPeriod).all()}

    months, y, m = [], today.year, today.month
    for _ in range(13):
        override = overrides.get((y, m))
        default_open = (y, m) >= (today.year, today.month)
        months.append(
            {
                "year": y,
                "month": m,
                "label": f"{y}-{m:02d}",
                "is_open": override.is_open if override else default_open,
                "is_current": (y, m) == (today.year, today.month),
                "overridden": override is not None,
                "changed_by": override.changed_by if override else None,
                "reason": override.reason if override else None,
            }
        )
        m -= 1
        if m == 0:
            m, y = 12, y - 1

    return _json({"periods": months, "can_change": current_user.role == "admin"})


@router.post("/financial-periods")
def set_period(
    body: dict | None = Body(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin"])),
):
    """Close a month early, or reopen a closed one. Admin only."""
    data = body or {}
    try:
        year, month = int(data["year"]), int(data["month"])
    except (KeyError, TypeError, ValueError):
        return _json({"error": "year and month are required"}, 400)
    if not 1 <= month <= 12:
        return _json({"error": "month must be between 1 and 12"}, 400)
    if "is_open" not in data:
        return _json({"error": "is_open is required"}, 400)

    is_open = bool(data["is_open"])
    reason = (data.get("reason") or "").strip()
    if is_open and not reason:
        return _json({"error": "Give a reason for reopening a closed month."}, 400)

    period = db.query(FinancialPeriod).filter_by(year=year, month=month).first()
    if not period:
        period = FinancialPeriod(year=year, month=month)
        db.add(period)

    period.is_open = is_open
    period.changed_by = current_user.username if current_user else None
    period.changed_at = datetime.utcnow()
    period.reason = reason or None
    db.flush()

    log_action(
        db,
        current_user,
        "REOPEN" if is_open else "CLOSE",
        "financial_periods",
        period.id,
        f"{'Reopened' if is_open else 'Closed'} {year}-{month:02d}"
        + (f": {reason}" if reason else ""),
    )
    db.commit()

    return _json({"period": period.to_dict()})
