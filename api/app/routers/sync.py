"""Sync: the cloud-facing push/pull (a branch server authenticates with its token) and the admin screens."""

import hashlib
import hmac
import secrets
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import sync, sync_worker
from app.auth import Actor, require
from app.db import get_db
from app.models import SyncConflict, SyncCredential, SyncInbox, SyncOutbox
from app.validators import Text

router = APIRouter(prefix="/api/sync", tags=["sync"])
can_sync = require("sync")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def branch_server(x_branch_id: str = Header(default=""), x_sync_token: str = Header(default=""), db: Session = Depends(get_db)) -> uuid.UUID:
    try:
        branch_id = uuid.UUID(x_branch_id)
    except ValueError:
        raise HTTPException(401, "Unknown branch server")
    cred = db.get(SyncCredential, branch_id)
    if not cred or not hmac.compare_digest(cred.token_hash, _hash(x_sync_token)):
        raise HTTPException(401, "Unknown branch server")
    return branch_id


# --- what a branch server calls (no login; the token is the credential) -------------------------

class EventIn(BaseModel):
    seq: int
    table: str
    row_id: uuid.UUID
    op: Literal["upsert", "delete"]
    payload: dict


class PushIn(BaseModel):
    events: list[EventIn] = Field(max_length=500)


@router.post("/push")
def push(body: PushIn, branch_id: uuid.UUID = Depends(branch_server), db: Session = Depends(get_db)):
    out = sync.apply_events(db, branch_id, [e.model_dump(mode="json") for e in body.events])
    db.commit()
    return out


@router.get("/pull")
def pull(cursor: int = 0, limit: int = Query(200, le=500), branch_id: uuid.UUID = Depends(branch_server), db: Session = Depends(get_db)):
    """Changes other branches made, in the order the cloud received them. Our own are not sent back."""
    scanned = list(db.scalars(select(SyncInbox).where(SyncInbox.seq > cursor).order_by(SyncInbox.seq).limit(limit)))
    rows = [r for r in scanned if r.origin_branch_id != branch_id and r.outcome == "applied"]
    nxt = scanned[-1].seq if scanned else cursor  # moves past rows we skipped too, so the cursor never stalls
    return {"events": [{"inbox_seq": r.seq, "origin_branch_id": str(r.origin_branch_id), "origin_seq": r.origin_seq, "table": r.table_name,
                        "row_id": str(r.row_id), "op": r.op, "payload": r.payload} for r in rows], "next_cursor": nxt}


# --- what people use ---------------------------------------------------------------------------

@router.get("/status")
def status(actor: Actor = Depends(can_sync), db: Session = Depends(get_db)):
    st = sync_worker.state_of(db, actor.branch)
    db.commit()
    oldest = db.scalar(select(func.min(SyncOutbox.created_at)).where(SyncOutbox.synced_at.is_(None)))
    return {"configured": sync_worker.configured(), "branch_id": actor.branch.id, "pending": sync_worker.pending(db), "oldest_pending_at": oldest,
            "last_push_at": st.last_push_at, "last_pull_at": st.last_pull_at, "last_error": st.last_error, "last_error_at": st.last_error_at,
            "open_conflicts": db.scalar(select(func.count()).select_from(SyncConflict).where(SyncConflict.status == "open"))}


@router.post("/run")
def run(actor: Actor = Depends(can_sync), db: Session = Depends(get_db)):
    if not sync_worker.configured():
        raise HTTPException(409, "Sync is not set up: the cloud address and token are missing from the server settings")
    return sync_worker.run_once(db, actor.branch, sync_worker.transport_for(actor.branch))


class TokenIn(BaseModel):
    branch_id: uuid.UUID


@router.post("/tokens", status_code=201)
def make_token(body: TokenIn, actor: Actor = Depends(can_sync), db: Session = Depends(get_db)):
    """Run on the cloud: makes (or replaces) the token a branch server uses. Shown once; only its hash is kept."""
    token = secrets.token_urlsafe(32)
    cred = db.get(SyncCredential, body.branch_id)
    if cred:
        cred.token_hash = _hash(token)
    else:
        db.add(SyncCredential(branch_id=body.branch_id, token_hash=_hash(token)))
    db.commit()
    return {"branch_id": body.branch_id, "token": token}


def _conflict_out(c: SyncConflict) -> dict:
    keys = sorted(k for k in c.local.keys() | c.remote.keys() if c.local.get(k) != c.remote.get(k) and k not in ("updated_at", "updated_by"))
    return {"id": c.id, "table": c.table_name, "row_id": c.row_id, "status": c.status, "resolution": c.resolution, "note": c.note,
            "created_at": c.created_at, "resolved_at": c.resolved_at, "local": c.local, "remote": c.remote, "differs": keys}


@router.get("/conflicts")
def conflicts(status: Literal["open", "resolved"] = "open", actor: Actor = Depends(can_sync), db: Session = Depends(get_db)):
    rows = db.scalars(select(SyncConflict).where(SyncConflict.status == status).order_by(SyncConflict.created_at.desc()).limit(200))
    return [_conflict_out(c) for c in rows]


class ResolveIn(BaseModel):
    resolution: Literal["keep_local", "keep_remote"]
    note: Text = Field(default="", max_length=500)


@router.post("/conflicts/{conflict_id}/resolve")
def resolve(conflict_id: uuid.UUID, body: ResolveIn, actor: Actor = Depends(can_sync), db: Session = Depends(get_db)):
    c = db.scalar(select(SyncConflict).where(SyncConflict.id == conflict_id).with_for_update())
    if not c:
        raise HTTPException(404, "Conflict not found")
    if c.status != "open":
        raise HTTPException(409, "Already settled")
    sync.resolve(db, c, body.resolution, body.note, actor.user.id)
    db.commit()
    return _conflict_out(c)
