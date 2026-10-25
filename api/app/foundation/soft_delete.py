"""Soft-delete helpers. Prefer deleted_at over hard DELETE for new entities."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Query


def not_deleted(query: Query, model) -> Query:
    if not hasattr(model, "deleted_at"):
        return query
    return query.filter(model.deleted_at.is_(None))


def soft_delete(entity, *, by: str | None = None) -> None:
    if not hasattr(entity, "deleted_at"):
        raise TypeError(f"{type(entity).__name__} has no deleted_at")
    entity.deleted_at = datetime.utcnow()
    if by and hasattr(entity, "updated_by"):
        entity.updated_by = by
    if hasattr(entity, "updated_at"):
        entity.updated_at = datetime.utcnow()
    if hasattr(entity, "version") and entity.version is not None:
        entity.version = int(entity.version) + 1
