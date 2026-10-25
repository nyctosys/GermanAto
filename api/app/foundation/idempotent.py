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


def _resolve_request_db(args, kwargs) -> tuple[Request | None, Session | None]:
    request: Request | None = kwargs.get("request")
    db: Session | None = kwargs.get("db")
    if request is None or db is None:
        for arg in args:
            if isinstance(arg, Request):
                request = arg
            elif isinstance(arg, Session):
                db = arg
    return request, db


def _store_if_needed(db: Session, request: Request, key: str | None, result: Any) -> Any:
    if not key:
        return result
    branch_id = get_branch()
    user = get_user()
    created_by = getattr(user, "username", None) if user else None

    if isinstance(result, JSONResponse):
        status = result.status_code
        body: Any = result.body
        try:
            import json

            body = (
                json.loads(body.decode("utf-8"))
                if isinstance(body, (bytes, bytearray))
                else body
            )
        except Exception:
            body = {"ok": True}
        if 200 <= status < 300:
            store_response(
                db,
                key=key,
                request=request,
                status=status,
                body=body,
                branch_id=branch_id,
                created_by=created_by,
            )
            try:
                db.commit()
            except Exception:
                db.rollback()
        return result

    if isinstance(result, dict):
        store_response(
            db,
            key=key,
            request=request,
            status=201,
            body=result,
            branch_id=branch_id,
            created_by=created_by,
        )
    return result


def idempotent_create(fn: Callable) -> Callable:
    """Wrap a create (or payment) route: replay prior response when Idempotency-Key repeats.

    Supports both sync and async route handlers.
    """

    if inspect.iscoroutinefunction(fn):

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            request, db = _resolve_request_db(args, kwargs)
            if request is None or db is None:
                return await fn(*args, **kwargs)

            key = get_idempotency_key(request)
            replay = replay_if_seen(db, key=key, request=request, branch_id=get_branch())
            if replay is not None:
                return replay

            result = await fn(*args, **kwargs)
            return _store_if_needed(db, request, key, result)

        async_wrapper.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
        return async_wrapper

    @wraps(fn)
    def wrapper(*args, **kwargs):
        request, db = _resolve_request_db(args, kwargs)
        if request is None or db is None:
            return fn(*args, **kwargs)

        key = get_idempotency_key(request)
        replay = replay_if_seen(db, key=key, request=request, branch_id=get_branch())
        if replay is not None:
            return replay

        result = fn(*args, **kwargs)
        return _store_if_needed(db, request, key, result)

    wrapper.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
    return wrapper
