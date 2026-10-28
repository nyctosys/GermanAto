"""One flush hook writes the audit trail and the sync outbox for every change
to an Entity, inside the same transaction. Routes can't forget to log, and
nothing reaches the database without a matching outbox row."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import event, insert, inspect
from sqlalchemy.orm import Session

from app.db import BranchScoped, Entity, utcnow, uuid7
from app.models import AuditLog, SyncOutbox

_SKIP_IN_DIFF = {"updated_at", "updated_by", "version"}


def jsonable(value):
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def row_dict(obj) -> dict:
    return {c.key: jsonable(getattr(obj, c.key)) for c in inspect(obj).mapper.column_attrs}


def _diff(obj, excluded: set[str]) -> dict:
    changes = {}
    for attr in inspect(obj).attrs:
        if attr.key in excluded or attr.key in _SKIP_IN_DIFF or not hasattr(attr, "history"):
            continue
        hist = attr.history
        if hist.has_changes() and attr.key in inspect(obj).mapper.column_attrs:
            old = hist.deleted[0] if hist.deleted else None
            new = hist.added[0] if hist.added else None
            changes[attr.key] = [jsonable(old), jsonable(new)]
    return changes


def log_action(db: Session, action: str, entity_type: str, entity_id=None, details: dict | None = None,
               user_id=None, branch_id=None) -> None:
    """Audit an action that changes no row (login, failed login, print, export)."""
    db.add(AuditLog(
        action=action, entity_type=entity_type, entity_id=entity_id, changes=details or {},
        user_id=user_id or db.info.get("user_id"), branch_id=branch_id or db.info.get("branch_id"),
        ip=db.info.get("ip", ""),
    ))


@event.listens_for(Session, "before_flush")
def _stamp(session: Session, _ctx, _instances):
    user_id, branch_id = session.info.get("user_id"), session.info.get("branch_id")
    for obj in session.new:
        if isinstance(obj, Entity):
            obj.created_by = obj.created_by or user_id
            obj.updated_by = obj.updated_by or user_id
        if isinstance(obj, BranchScoped) and obj.branch_id is None:
            if branch_id is None:
                raise ValueError(f"{type(obj).__name__} needs a branch but nobody is signed in to one")
            obj.branch_id = branch_id
    for obj in session.dirty:
        if isinstance(obj, Entity) and session.is_modified(obj, include_collections=False):
            obj.updated_by = user_id


@event.listens_for(Session, "after_flush")
def _audit_and_outbox(session: Session, _ctx):
    audit_rows, outbox_rows = [], []
    for kind, objs in (("create", session.new), ("update", session.dirty), ("delete", session.deleted)):
        for obj in objs:
            if not isinstance(obj, Entity):
                continue
            excluded = getattr(obj, "__audit_exclude__", set())
            data = row_dict(obj)
            if kind == "update":
                if not session.is_modified(obj, include_collections=False):
                    continue  # touched but unchanged
                changes = _diff(obj, excluded)  # may be empty: only excluded columns moved
            else:
                changes = {k: v for k, v in data.items() if k not in excluded}
            if changes:
                audit_rows.append({
                    "id": uuid7(), "at": utcnow(), "branch_id": getattr(obj, "branch_id", None) or session.info.get("branch_id"),
                    "user_id": session.info.get("user_id"), "action": kind, "entity_type": obj.__tablename__,
                    "entity_id": obj.id, "changes": changes, "ip": session.info.get("ip", ""),
                })
            outbox_rows.append({
                "table_name": obj.__tablename__, "row_id": obj.id,
                "op": "delete" if kind == "delete" else "upsert", "payload": data,
            })
    conn = session.connection()
    if audit_rows:
        conn.execute(insert(AuditLog), audit_rows)
    if outbox_rows:
        conn.execute(insert(SyncOutbox), outbox_rows)
