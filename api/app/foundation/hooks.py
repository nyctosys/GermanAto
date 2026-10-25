"""
Session-level foundation hooks:

- Soft-delete via Session.delete when deleted_at exists
- Auto-assign branch_id on insert
- Automatic AppLog audit (old/new) on flush
- Require audit reason for price/stock/delete overrides
- ORM select criteria: exclude soft-deleted + scope to current branch
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, with_loader_criteria

from app.foundation.audit import audit_write
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import (
    current_branch_id,
    current_reason,
    get_branch,
    get_reason,
    get_user,
    include_deleted,
    skip_audit,
    skip_branch_scope,
)
from app.foundation.soft_delete import soft_delete as mark_soft_deleted

logger = logging.getLogger(__name__)

_SENSITIVE = frozenset(
    {
        "price",
        "amount",
        "rate",
        "quantity",
        "net_total",
        "balance",
        "advance",
        "discount",
        "paid_amount",
        "tax_amount",
        "debit",
        "credit",
        "salary",
        "earned_salary",
        "net_paid",
    }
)

_SKIP_AUDIT_TABLES = frozenset({"app_logs", "idempotency_keys", "role_permissions"})

_HOOKS_INSTALLED = False
_original_delete = Session.delete


def _entity_dict(obj) -> dict[str, Any]:
    state = inspect(obj)
    data: dict[str, Any] = {}
    for attr in state.mapper.column_attrs:
        key = attr.key
        if key in ("password_hash",):
            continue
        try:
            data[key] = state.attrs[key].value
        except Exception:
            continue
    return data


def _module_name(obj) -> str:
    return getattr(obj, "__tablename__", type(obj).__name__)


def _require_reason(action: str, changed: set[str] | None = None) -> None:
    needs = action == "DELETE" or (changed and bool(changed & _SENSITIVE))
    if not needs:
        return
    reason = (get_reason() or "").strip()
    if not reason:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail={
                "error": (
                    "reason is required for price edits, discounts above threshold, "
                    "stock adjustments, deletes, payment-gate overrides, "
                    "evidence exceptions, and period reopen"
                ),
                "require_reason": True,
            },
        )


def _soft_aware_delete(self: Session, instance: Any) -> None:
    if hasattr(instance, "deleted_at"):
        _require_reason("DELETE")
        user = get_user()
        by = getattr(user, "username", None) if user else None
        mark_soft_deleted(instance, by=by)
        if instance not in self:
            self.add(instance)
        return None
    return _original_delete(self, instance)


def _before_flush(session: Session, flush_context, instances) -> None:
    bid = get_branch() or DEFAULT_BRANCH_ID
    user = get_user()
    reason = get_reason()

    from app.models import FoundationMixin

    for obj in list(session.new):
        # Only FoundationMixin rows get auto branch/version (not AppSetting / AppLog).
        if isinstance(obj, FoundationMixin):
            if not getattr(obj, "branch_id", None):
                obj.branch_id = bid
            if getattr(obj, "version", None) is None:
                obj.version = 1
        if skip_audit.get() or _module_name(obj) in _SKIP_AUDIT_TABLES:
            continue
        if type(obj).__name__ == "AppLog":
            continue
        audit_write(
            session,
            user=user,
            action="CREATE",
            module=_module_name(obj),
            reference_id=getattr(obj, "id", None),
            details=f"Created {_module_name(obj)}",
            new_value=_entity_dict(obj),
            reason=reason,
            branch_id=getattr(obj, "branch_id", None) or bid,
            flush=False,
        )

    for obj in list(session.dirty):
        if skip_audit.get() or _module_name(obj) in _SKIP_AUDIT_TABLES:
            continue
        if type(obj).__name__ == "AppLog":
            continue
        state = inspect(obj)
        if not state.modified:
            continue
        changed: set[str] = set()
        old_snap: dict[str, Any] = {}
        new_snap: dict[str, Any] = {}
        for attr in state.mapper.column_attrs:
            hist = state.attrs[attr.key].history
            if hist.has_changes():
                changed.add(attr.key)
                old_snap[attr.key] = hist.deleted[0] if hist.deleted else None
                new_snap[attr.key] = hist.added[0] if hist.added else getattr(obj, attr.key, None)
        if not changed:
            continue
        # Soft-delete is DELETE; other sensitive edits need reason
        action = "DELETE" if "deleted_at" in changed and new_snap.get("deleted_at") else "UPDATE"
        if action == "UPDATE" and "version" in changed and len(changed) == 1:
            continue
        try:
            _require_reason(action, changed)
        except Exception:
            # Re-raise HTTPException; swallow nothing here
            raise
        audit_write(
            session,
            user=user,
            action=action,
            module=_module_name(obj),
            reference_id=getattr(obj, "id", None),
            details=f"{action} {_module_name(obj)} fields={sorted(changed)}",
            old_value=old_snap,
            new_value=new_snap,
            reason=reason,
            branch_id=getattr(obj, "branch_id", None) or bid,
            flush=False,
        )


def _do_orm_execute(execute_state) -> None:
    if not execute_state.is_select:
        return
    if execute_state.is_column_load or execute_state.is_relationship_load:
        return
    apply_deleted = not (
        execute_state.execution_options.get("include_deleted", False) or include_deleted.get()
    )
    apply_branch = not (
        execute_state.execution_options.get("skip_branch_scope", False) or skip_branch_scope.get()
    )
    bid = current_branch_id.get()

    from app.models import FoundationMixin

    # Separate options avoid uncacheable boolean closures inside one lambda.
    if apply_deleted:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                FoundationMixin,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )
    if apply_branch and bid:
        branch_id = bid
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                FoundationMixin,
                lambda cls: cls.branch_id == branch_id,
                include_aliases=True,
                track_closure_variables=False,
            )
        )


def install_foundation_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    Session.delete = _soft_aware_delete  # type: ignore[method-assign]
    event.listen(Session, "before_flush", _before_flush)
    event.listen(Session, "do_orm_execute", _do_orm_execute)
    _HOOKS_INSTALLED = True
    logger.info("Foundation session hooks installed")
