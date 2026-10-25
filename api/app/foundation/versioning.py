"""Optimistic locking via integer `version` column."""

from __future__ import annotations

from fastapi import HTTPException


class VersionConflict(HTTPException):
    def __init__(self, current: int | None = None):
        super().__init__(
            status_code=409,
            detail={
                "error": "Version conflict — record was modified by someone else. Reload and try again.",
                "conflict": True,
                "current_version": current,
            },
        )


def check_version(entity, expected: int | None) -> None:
    """Raise 409 if client version does not match. No-op when expected is None (legacy clients)."""
    if expected is None:
        return
    if not hasattr(entity, "version"):
        return
    current = int(entity.version or 1)
    try:
        expected_i = int(expected)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="version must be an integer") from exc
    if expected_i != current:
        raise VersionConflict(current)


def bump_version(entity) -> int:
    if not hasattr(entity, "version"):
        return 0
    entity.version = int(entity.version or 1) + 1
    return entity.version


def extract_version(data: dict | None) -> int | None:
    if not data:
        return None
    if "version" not in data:
        return None
    raw = data.get("version")
    if raw is None or raw == "":
        return None
    return int(raw)
