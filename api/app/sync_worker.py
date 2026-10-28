"""The branch server's sync worker: push what is in the outbox, then pull what other branches did.
Runs forever as its own container (`python -m app.sync_worker`), or once on demand from the Sync page."""

import json
import os
import time
import urllib.request
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import sync
from app.db import SessionLocal
from app.models import Branch, SyncOutbox, SyncState

BATCH = 200


class HttpTransport:
    def __init__(self, url: str, token: str, branch_id: uuid.UUID):
        self.url, self.headers = url.rstrip("/"), {"X-Sync-Token": token, "X-Branch-Id": str(branch_id), "Content-Type": "application/json"}

    def _call(self, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None, headers=self.headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def push(self, events: list[dict]) -> dict:
        return self._call("/api/sync/push", {"events": events})

    def pull(self, cursor: int) -> dict:
        return self._call(f"/api/sync/pull?cursor={cursor}&limit={BATCH}")


def configured() -> bool:
    return bool(os.environ.get("SYNC_CLOUD_URL") and os.environ.get("SYNC_TOKEN"))


def transport_for(branch: Branch) -> HttpTransport:
    return HttpTransport(os.environ["SYNC_CLOUD_URL"], os.environ["SYNC_TOKEN"], branch.id)


def state_of(db: Session, branch: Branch) -> SyncState:
    st = db.get(SyncState, branch.id)
    if not st:
        st = SyncState(branch_id=branch.id, pull_cursor=0, last_error="")
        db.add(st)
        db.flush()
    return st


def run_once(db: Session, branch: Branch, transport) -> dict:
    """One round: push everything waiting, then pull everything new. A failure is recorded and nothing is lost:
    unsent events stay in the outbox and the cursor only moves after a pulled batch is applied."""
    st = state_of(db, branch)
    pushed = pulled = 0
    now = lambda: datetime.now(timezone.utc)  # noqa: E731
    try:
        while True:
            rows = list(db.scalars(select(SyncOutbox).where(SyncOutbox.synced_at.is_(None)).order_by(SyncOutbox.seq).limit(BATCH)))
            if not rows:
                break
            resp = transport.push([{"seq": r.seq, "table": r.table_name, "row_id": str(r.row_id), "op": r.op, "payload": r.payload} for r in rows])
            if resp["acked"]:
                done = [r.seq for r in rows if r.seq <= resp["acked"]]
                db.execute(update(SyncOutbox).where(SyncOutbox.seq.in_(done)).values(synced_at=now()))
                pushed += len(done)
                st.last_push_at = now()
            db.commit()
            if resp.get("error"):
                raise RuntimeError("The cloud refused " + resp["error"])
            if len(rows) < BATCH:
                break
        while True:
            resp = transport.pull(st.pull_cursor)
            if resp["next_cursor"] == st.pull_cursor:
                break
            for ev in resp["events"]:  # the cloud sends them in its own order; each carries its origin
                out = sync.apply_events(db, uuid.UUID(ev["origin_branch_id"]), [{**ev, "seq": ev["origin_seq"]}])
                if out["error"]:
                    raise RuntimeError(out["error"])
                pulled += 1
            st.pull_cursor, st.last_pull_at = resp["next_cursor"], now()
            db.commit()
        st.last_error = ""
    except Exception as e:  # noqa: BLE001
        db.rollback()
        st = state_of(db, branch)
        st.last_error, st.last_error_at = str(e)[:500], now()
        db.commit()
        return {"pushed": pushed, "pulled": pulled, "error": st.last_error}
    db.commit()
    return {"pushed": pushed, "pulled": pulled, "error": ""}


def pending(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(SyncOutbox).where(SyncOutbox.synced_at.is_(None)))


def main() -> None:
    interval, wait = int(os.environ.get("SYNC_INTERVAL_SECONDS", "60")), 0
    while True:
        time.sleep(wait or interval)
        if not configured():
            wait = interval
            continue
        with SessionLocal() as db:
            branch = db.scalar(select(Branch).where(Branch.is_active))
            if not branch:
                continue
            out = run_once(db, branch, transport_for(branch))
        # after a failure wait longer each time (up to 15 minutes) so a dead link isn't hammered
        wait = min(max(wait, interval) * 2, 900) if out["error"] else 0
        print(f"sync: pushed {out['pushed']}, pulled {out['pulled']}" + (f", error: {out['error']}" if out["error"] else ""), flush=True)


if __name__ == "__main__":
    main()
