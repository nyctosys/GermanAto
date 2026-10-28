"""Idempotency-Key support for every POST, PUT and PATCH. A client sends a fresh key for each thing the person
does; if the same request is sent again with that key (a double click, a retry after a dropped connection)
the first answer is returned and nothing is done twice. Only successful answers are kept, so fixing a
mistake and trying again still works. A key is tied to the signed-in session and to the exact request."""

import hashlib
import re
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from starlette.concurrency import run_in_threadpool

from app.auth import COOKIE
from app.db import SessionLocal, utcnow
from app.models import IdempotencyKey

KEEP = timedelta(hours=24)
_COOKIE = re.compile(rb"(?:^|;\s*)" + COOKIE.encode() + rb"=([^;]+)")


def _claim(scope: str, key: str, request_hash: str):
    """Returns ('new', id), ('replay', row) or ('busy'/'mismatch', None)."""
    with SessionLocal() as db:
        db.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < utcnow() - KEEP))
        got = db.execute(insert(IdempotencyKey).values(scope=scope, key=key, request_hash=request_hash)
                         .on_conflict_do_nothing(index_elements=["scope", "key"]).returning(IdempotencyKey.id)).scalar()
        db.commit()
        if got:
            return "new", got
        row = db.scalar(select(IdempotencyKey).where(IdempotencyKey.scope == scope, IdempotencyKey.key == key))
        if row.request_hash != request_hash:
            return "mismatch", None
        if row.status_code is None:
            return "busy", None
        return "replay", (row.status_code, row.content_type, row.body)


def _finish(row_id, status: int | None, content_type: str, body: str) -> None:
    with SessionLocal() as db:
        if status is None:  # not a success: forget the key so the person can try again
            db.execute(delete(IdempotencyKey).where(IdempotencyKey.id == row_id))
        else:
            db.execute(IdempotencyKey.__table__.update().where(IdempotencyKey.id == row_id)
                       .values(status_code=status, content_type=content_type, body=body))
        db.commit()


async def _reply(send, status: int, body: bytes, content_type: str = "application/json", replayed: bool = False):
    headers = [(b"content-type", content_type.encode()), (b"content-length", str(len(body)).encode())]
    if replayed:
        headers.append((b"idempotency-replayed", b"true"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class IdempotencyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        key = headers.get(b"idempotency-key", b"").decode()
        cookie = _COOKIE.search(headers.get(b"cookie", b""))
        if not key or not cookie or len(key) > 80 or scope["path"].startswith("/api/auth/"):
            return await self.app(scope, receive, send)

        chunks, more = [], True
        while more:  # read the whole body so it can be hashed, then handed on unchanged
            msg = await receive()
            chunks.append(msg.get("body", b""))
            more = msg.get("more_body", False)
        body = b"".join(chunks)
        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        scope_id = hashlib.sha256(cookie.group(1)).hexdigest()
        request_hash = hashlib.sha256(scope["method"].encode() + scope["path"].encode() + scope["query_string"] + body).hexdigest()
        state, got = await run_in_threadpool(_claim, scope_id, key, request_hash)
        if state == "mismatch":
            return await _reply(send, 422, b'{"detail":"This Idempotency-Key was already used for a different request"}')
        if state == "busy":
            return await _reply(send, 409, b'{"detail":"This request is already being processed"}')
        if state == "replay":
            status, content_type, text = got
            return await _reply(send, status, text.encode(), content_type, replayed=True)

        status, content_type, parts = 500, "application/json", []

        async def capture(message):
            nonlocal status, content_type
            if message["type"] == "http.response.start":
                status = message["status"]
                content_type = dict(message["headers"]).get(b"content-type", b"application/json").decode()
            elif message["type"] == "http.response.body":
                parts.append(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, replay, capture)
        except BaseException:
            await run_in_threadpool(_finish, got, None, "", "")
            raise
        ok = 200 <= status < 300
        await run_in_threadpool(_finish, got, status if ok else None, content_type, b"".join(parts).decode() if ok else "")
