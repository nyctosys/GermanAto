"""Shared list/get scoping: branch + soft-delete. Prefer this over ad-hoc filters."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Query, Session

from app.foundation.branch import DEFAULT_BRANCH_ID, for_branch
from app.foundation.context import get_branch
from app.foundation.soft_delete import not_deleted


def resolve_branch_id(explicit: str | None = None) -> str:
    return explicit or get_branch() or DEFAULT_BRANCH_ID


def scoped_query(
    db: Session,
    model,
    branch_id: str | None = None,
    *,
    include_deleted: bool = False,
) -> Query:
    """Base query for list endpoints: active rows in the current branch."""
    q = db.query(model)
    bid = resolve_branch_id(branch_id)
    q = for_branch(q, model, bid)
    if not include_deleted:
        q = not_deleted(q, model)
    return q


def get_active(
    db: Session,
    model,
    pk,
    branch_id: str | None = None,
    *,
    include_deleted: bool = False,
):
    """Load one row; 404 if missing, wrong branch, or soft-deleted."""
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    if hasattr(obj, "deleted_at") and obj.deleted_at is not None and not include_deleted:
        raise HTTPException(status_code=404, detail="Not found")
    bid = resolve_branch_id(branch_id)
    if hasattr(obj, "branch_id") and obj.branch_id and obj.branch_id != bid:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


def assign_branch(entity, branch_id: str | None = None) -> None:
    if hasattr(entity, "branch_id") and not getattr(entity, "branch_id", None):
        entity.branch_id = resolve_branch_id(branch_id)
