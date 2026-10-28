"""Applying changes that came from another server (the cloud, or a branch via the cloud).

Rules, per incoming row:
- newer version than ours: take it;  older: ignore it (we already have better);
- same version but different content: both sides changed it independently -> keep ours, record a conflict for a person to settle.
Changes are written with Core statements, which skip the audit/outbox hook, so a pulled change is never pushed back out.
The (origin branch, origin seq) pair is recorded for every event, so replaying a batch changes nothing.
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy import Date, DateTime, Numeric, Time, Uuid

from app.db import Base
from app.events import jsonable
from app.models import SyncConflict, SyncInbox, SyncOutbox

IGNORED_IN_COMPARE = {"updated_at", "updated_by"}


def _coerce(col, value):
    if value is None or isinstance(col.type, JSONB):
        return value
    t = col.type
    if isinstance(t, Uuid):
        return uuid.UUID(value)
    if isinstance(t, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(t, Date):
        return date.fromisoformat(value)
    if isinstance(t, Time):
        return time.fromisoformat(value)
    if isinstance(t, Numeric):
        return Decimal(value)
    return value


def _values(table, payload: dict) -> dict:
    return {c.name: _coerce(c, payload[c.name]) for c in table.columns if c.name in payload}


def _same(table, row, payload: dict) -> bool:
    return all(jsonable(row[c.name]) == payload.get(c.name) for c in table.columns
               if c.name not in IGNORED_IN_COMPARE and c.name in payload)


def apply_event(db: Session, origin: uuid.UUID, ev: dict) -> str:
    """Applies one event; returns 'applied', 'stale', 'conflict' or 'duplicate'."""
    if db.scalar(select(SyncInbox.seq).where(SyncInbox.origin_branch_id == origin, SyncInbox.origin_seq == ev["seq"])):
        return "duplicate"
    table = Base.metadata.tables.get(ev["table"])
    if table is None:
        raise ValueError(f"Unknown table {ev['table']}")
    row_id = uuid.UUID(str(ev["row_id"]))
    payload = ev["payload"]
    existing = db.execute(select(table).where(table.c.id == row_id)).mappings().first()
    if ev["op"] == "delete":
        outcome = "applied"
        if existing is not None:
            db.execute(delete(table).where(table.c.id == row_id))
    elif existing is None:
        db.execute(insert(table).values(**_values(table, payload)))
        outcome = "applied"
    elif payload["version"] > existing["version"]:
        db.execute(update(table).where(table.c.id == row_id).values(**_values(table, payload)))
        outcome = "applied"
    elif payload["version"] < existing["version"] or _same(table, existing, payload):
        outcome = "stale"
    else:
        db.add(SyncConflict(origin_branch_id=origin, table_name=ev["table"], row_id=row_id,
                            local={k: jsonable(v) for k, v in existing.items()}, remote=payload))
        outcome = "conflict"
    db.add(SyncInbox(origin_branch_id=origin, origin_seq=ev["seq"], table_name=ev["table"], row_id=row_id, op=ev["op"],
                     payload=payload, outcome=outcome))
    db.flush()
    return outcome


def apply_events(db: Session, origin: uuid.UUID, events: list[dict]) -> dict:
    """Applies events in order, each in its own savepoint. Stops at the first failure so order is never broken;
    `acked` is the last seq that is safely done, and the sender resends everything after it."""
    out = {"acked": 0, "applied": 0, "stale": 0, "conflict": 0, "duplicate": 0, "error": ""}
    for ev in sorted(events, key=lambda e: e["seq"]):
        try:
            with db.begin_nested():
                out[apply_event(db, origin, ev)] += 1
        except Exception as e:  # noqa: BLE001  a bad event stops the batch; the sender keeps it and retries
            out["error"] = f"seq {ev['seq']} ({ev['table']}): {str(e)[:300]}"
            break
        out["acked"] = ev["seq"]
    return out


def resolve(db: Session, conflict: SyncConflict, resolution: str, note: str, user_id) -> None:
    """keep_remote overwrites our row with the other server's; keep_local bumps our version so our content wins
    everywhere (it is queued to go out, and the other side will take the higher version)."""
    table = Base.metadata.tables[conflict.table_name]
    if resolution == "keep_remote":
        db.execute(update(table).where(table.c.id == conflict.row_id).values(**_values(table, conflict.remote)))
    else:
        db.execute(update(table).where(table.c.id == conflict.row_id).values(version=table.c.version + 1))
        row = db.execute(select(table).where(table.c.id == conflict.row_id)).mappings().first()
        db.add(SyncOutbox(table_name=conflict.table_name, row_id=conflict.row_id, op="upsert",
                          payload={k: jsonable(v) for k, v in row.items()}))
    conflict.status, conflict.resolution, conflict.note = "resolved", resolution, note
    conflict.resolved_by, conflict.resolved_at = user_id, datetime.now().astimezone()
