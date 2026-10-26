"""Unauthenticated tokenized quote approval API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.quote_approval import apply_line_decisions, public_quote_payload, resolve_token

router = APIRouter(tags=["public-quotes"])


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


@router.get("/public/quotes/{token}")
def get_public_quote(token: str, db: Session = Depends(get_db)):
    _tok, invoice = resolve_token(db, token)
    return _json(public_quote_payload(invoice))


@router.post("/public/quotes/{token}/decide")
def decide_public_quote(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
):
    _tok, invoice = resolve_token(db, token)
    data = body or {}
    decisions = data.get("decisions") or []
    client_ip = request.headers.get("X-Forwarded-For") or (
        request.client.host if request.client else None
    )
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    payload = apply_line_decisions(
        db, invoice, decisions, token=token, client_ip=client_ip, user=None
    )
    db.commit()
    return _json(payload)
