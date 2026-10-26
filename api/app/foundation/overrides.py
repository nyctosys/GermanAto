"""Guards for sensitive overrides that require audit reason (+ often a permission)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.foundation.context import get_reason
from app.foundation.settings import discount_needs_approval, payment_gate_enabled

# Override kinds that always require X-Audit-Reason (or body reason).
OVERRIDE_KINDS = frozenset(
    {
        "price_edit",
        "discount_above_threshold",
        "stock_adjustment",
        "delete",
        "payment_gate",
        "evidence_exception",
        "period_reopen",
        "qc_signoff",
    }
)

# Map override kind → permission key (owner/admin always pass).
OVERRIDE_PERMISSIONS: dict[str, str] = {
    "discount_above_threshold": "approve_discount",
    "payment_gate": "override_payment_gate",
    "stock_adjustment": "adjust_stock",
    "period_reopen": "reopen_period",
    "evidence_exception": "approve_evidence_exception",
    # qc_signoff is used by QC flows; price_edit / delete use reason only via hooks
    "qc_signoff": "qc_signoff",
}


def require_audit_reason(*, kind: str | None = None, reason: str | None = None) -> str:
    """Require a non-empty reason; raise 400 with require_reason flag."""
    text = (reason if reason is not None else get_reason() or "").strip()
    if not text:
        label = kind.replace("_", " ") if kind else "this override"
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"reason is required for {label}",
                "require_reason": True,
                "override_kind": kind,
            },
        )
    return text


def user_has_permission(db: Session, user, permission: str) -> bool:
    from app.foundation.roles import ADMIN_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS
    from app.models import RolePermission
    from sqlalchemy import select

    if user is None:
        return False
    role = getattr(user, "role", None)
    if role in ("admin", "owner"):
        return True
    try:
        rows = db.scalars(
            select(RolePermission.permission).where(RolePermission.role == role)
        ).all()
        if rows:
            return permission in rows
        # Empty table → fall back to defaults for this role
        if db.scalar(select(RolePermission.id)) is None:
            return permission in DEFAULT_ROLE_PERMISSIONS.get(role, [])
        return False
    except Exception:
        return permission in DEFAULT_ROLE_PERMISSIONS.get(role, ADMIN_PERMISSIONS)


def require_override(
    db: Session,
    user,
    kind: str,
    *,
    reason: str | None = None,
) -> str:
    """Enforce reason (+ permission when mapped) for a named override."""
    if kind not in OVERRIDE_KINDS and kind not in OVERRIDE_PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"unknown override kind: {kind}")
    text = require_audit_reason(kind=kind, reason=reason)
    perm = OVERRIDE_PERMISSIONS.get(kind)
    if perm and not user_has_permission(db, user, perm):
        raise HTTPException(
            status_code=403,
            detail={
                "error": f"Missing permission: {perm}",
                "permission": perm,
                "override_kind": kind,
            },
        )
    return text


def assert_discount_override(
    db: Session,
    user,
    discount_pct: float,
    *,
    reason: str | None = None,
    branch_id: str | None = None,
) -> str | None:
    """If discount exceeds threshold, require manager permission + reason. Returns reason used."""
    if not discount_needs_approval(db, discount_pct, branch_id=branch_id):
        return None
    return require_override(db, user, "discount_above_threshold", reason=reason)


def assert_payment_gate_override(
    db: Session,
    user,
    *,
    bypass: bool,
    reason: str | None = None,
    branch_id: str | None = None,
) -> str | None:
    """When payment gate is on and caller requests bypass, require permission + reason."""
    if not bypass or not payment_gate_enabled(db, branch_id=branch_id):
        return None
    return require_override(db, user, "payment_gate", reason=reason)
