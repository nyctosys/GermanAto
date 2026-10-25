"""Idempotency-Key helper for create endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.foundation.branch import DEFAULT_BRANCH_ID


def get_idempotency_key(request: Request) -> str | None:
    return request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")


def replay_if_seen(
    db: Session,
    *,
    key: str | None,
    request: Request,
    branch_id: str | None = None,
) -> JSONResponse | None:
    if not key:
        return None
    from app.models import IdempotencyKey

    row = (
        db.query(IdempotencyKey)
        .filter_by(branch_id=branch_id or DEFAULT_BRANCH_ID, key=key)
        .first()
    )
    if not row:
        return None
    try:
        body = json.loads(row.response_body)
    except json.JSONDecodeError:
        body = {"message": row.response_body}
    return JSONResponse(body, status_code=row.response_status)


def store_response(
    db: Session,
    *,
    key: str | None,
    request: Request,
    status: int,
    body: Any,
    branch_id: str | None = None,
    created_by: str | None = None,
) -> None:
    if not key:
        return
    from app.models import IdempotencyKey

    existing = (
        db.query(IdempotencyKey)
        .filter_by(branch_id=branch_id or DEFAULT_BRANCH_ID, key=key)
        .first()
    )
    if existing:
        return
    db.add(
        IdempotencyKey(
            branch_id=branch_id or DEFAULT_BRANCH_ID,
            key=key,
            method=request.method,
            path=str(request.url.path),
            response_status=status,
            response_body=json.dumps(body, default=str),
            created_by=created_by,
        )
    )
    db.flush()
