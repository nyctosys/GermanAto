"""Decorator / helpers to honor Idempotency-Key on create endpoints."""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.foundation.context import get_branch, get_user
from app.foundation.idempotency import get_idempotency_key, replay_if_seen, store_response


def idempotent_create(fn: Callable) -> Callable:
    """Wrap a create route: replay prior response when Idempotency-Key repeats."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        request: Request | None = kwargs.get("request")
        db: Session | None = kwargs.get("db")
        if request is None or db is None:
            # Positional fallback for unusual signatures
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif isinstance(arg, Session):
                    db = arg
        if request is None or db is None:
            return fn(*args, **kwargs)

        key = get_idempotency_key(request)
        branch_id = get_branch()
        replay = replay_if_seen(db, key=key, request=request, branch_id=branch_id)
        if replay is not None:
            return replay

        result = fn(*args, **kwargs)

        status = 200
        body: Any = result
        if isinstance(result, JSONResponse):
            status = result.status_code
            try:
                body = result.body
                import json

                body = json.loads(body.decode("utf-8")) if isinstance(body, (bytes, bytearray)) else body
            except Exception:
                body = {"ok": True}
            if 200 <= status < 300 and key:
                user = get_user()
                store_response(
                    db,
                    key=key,
                    request=request,
                    status=status,
                    body=body,
                    branch_id=branch_id,
                    created_by=getattr(user, "username", None) if user else None,
                )
                try:
                    db.commit()
                except Exception:
                    db.rollback()
        elif isinstance(result, dict) and key:
            user = get_user()
            store_response(
                db,
                key=key,
                request=request,
                status=201,
                body=result,
                branch_id=branch_id,
                created_by=getattr(user, "username", None) if user else None,
            )
        return result

    # Preserve FastAPI dependency injection markers
    wrapper.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
    return wrapper
