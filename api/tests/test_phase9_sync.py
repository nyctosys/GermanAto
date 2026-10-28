import uuid

import pytest
from sqlalchemy import func, select

from app import sync_worker
from app.db import SessionLocal, uuid7
from app.events import row_dict
from app.models import Branch, Customer, SyncOutbox, SyncState

REMOTE = str(uuid.uuid4())  # another branch server


def customer(admin, name="Local Ali", phone="0300-1111111"):
    c = admin.post("/api/customers", json={"name": name, "phone": phone, "kind": "individual"})
    assert c.status_code == 201, c.text
    return c.json()


def row(cid):
    with SessionLocal() as db:
        return row_dict(db.get(Customer, uuid.UUID(cid)))


def event(seq, payload, op="upsert", table="customers"):
    return {"seq": seq, "table": table, "row_id": payload["id"], "op": op, "payload": payload}


def new_remote(base, n=1, **over):
    return {**base, "id": str(uuid7()), "number": f"CUS-REMOTE-{n:06d}", "name": "Remote Sara", "phone": "+923002222222", **over}


@pytest.fixture
def headers(admin):
    tok = admin.post("/api/sync/tokens", json={"branch_id": REMOTE}).json()["token"]
    return {"X-Branch-Id": REMOTE, "X-Sync-Token": tok}


def push(admin, headers, events):
    r = admin.post("/api/sync/push", json={"events": events}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_branch_needs_its_token(admin, headers):
    assert admin.post("/api/sync/push", json={"events": []}).status_code == 401
    assert admin.post("/api/sync/push", json={"events": []}, headers={**headers, "X-Sync-Token": "guess"}).status_code == 401
    assert admin.get("/api/sync/pull", headers={"X-Branch-Id": "nonsense"}).status_code == 401
    assert admin.post("/api/sync/push", json={"events": []}, headers=headers).status_code == 200


def test_push_is_idempotent_and_newer_wins(admin, headers):
    base = row(customer(admin)["id"])
    r1 = new_remote(base)
    assert push(admin, headers, [event(1, r1)]) == {"acked": 1, "applied": 1, "stale": 0, "conflict": 0, "duplicate": 0, "error": ""}
    again = push(admin, headers, [event(1, r1)])
    assert again["duplicate"] == 1 and again["applied"] == 0 and again["acked"] == 1  # a resend changes nothing
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Customer).where(Customer.number == r1["number"])) == 1

    newer = {**r1, "name": "Remote Sara Khan", "version": 2}
    older = {**r1, "name": "ignored", "version": 1}
    out = push(admin, headers, [event(3, older), event(2, newer)])  # arrives out of order: sorted by seq first
    assert out["applied"] == 1 and out["stale"] == 1 and out["acked"] == 3
    assert row(r1["id"])["name"] == "Remote Sara Khan"


def test_a_bad_event_stops_the_batch_so_order_is_kept(admin, headers):
    base = row(customer(admin)["id"])
    good, later = new_remote(base, 1), new_remote(base, 2)
    out = push(admin, headers, [event(1, good), event(2, good, table="nope"), event(3, later)])
    assert out["acked"] == 1 and "seq 2" in out["error"] and out["applied"] == 1
    assert out["acked"] < 3 and row(good["id"]) and not _exists(later["id"])  # seq 3 waits behind the failure
    assert push(admin, headers, [event(3, later)])["acked"] == 3  # the sender retries after fixing the cause


def _exists(cid):
    with SessionLocal() as db:
        return db.get(Customer, uuid.UUID(cid)) is not None


def test_same_version_different_content_is_a_conflict_with_both_sides_kept(admin, headers):
    c = customer(admin)
    local = row(c["id"])
    out = push(admin, headers, [event(1, {**local, "name": "Remote Version"})])
    assert out["conflict"] == 1 and out["applied"] == 0
    assert row(c["id"])["name"] == "Local Ali"  # ours is untouched until a person decides
    [cf] = admin.get("/api/sync/conflicts").json()
    assert cf["table"] == "customers" and cf["local"]["name"] == "Local Ali" and cf["remote"]["name"] == "Remote Version" and cf["differs"] == ["name"]

    r = admin.post(f"/api/sync/conflicts/{cf['id']}/resolve", json={"resolution": "keep_remote", "note": "Sara spelled it right"})
    assert r.status_code == 200 and row(c["id"])["name"] == "Remote Version"
    assert admin.post(f"/api/sync/conflicts/{cf['id']}/resolve", json={"resolution": "keep_local"}).status_code == 409
    assert admin.get("/api/sync/conflicts").json() == [] and len(admin.get("/api/sync/conflicts?status=resolved").json()) == 1


def test_keeping_local_raises_the_version_and_queues_it_to_go_out(admin, headers):
    c = customer(admin, name="Keep Me")
    local = row(c["id"])
    push(admin, headers, [event(1, {**local, "name": "Other Name"})])
    [cf] = admin.get("/api/sync/conflicts").json()
    with SessionLocal() as db:
        before = db.scalar(select(func.max(SyncOutbox.seq)))
    assert admin.post(f"/api/sync/conflicts/{cf['id']}/resolve", json={"resolution": "keep_local"}).status_code == 200
    now = row(c["id"])
    assert now["name"] == "Keep Me" and now["version"] == local["version"] + 1
    with SessionLocal() as db:
        out = db.scalar(select(SyncOutbox).where(SyncOutbox.seq > before, SyncOutbox.row_id == uuid.UUID(c["id"])))
    assert out.payload["version"] == now["version"]  # the higher version wins on the other side


def test_pull_returns_other_branches_changes_after_the_cursor(admin, headers):
    base = row(customer(admin)["id"])
    push(admin, headers, [event(1, new_remote(base, 1)), event(2, new_remote(base, 2))])
    mine = admin.get("/api/sync/pull?cursor=0", headers=headers).json()
    assert mine["events"] == []  # a branch never gets its own changes back
    other = str(uuid.uuid4())
    tok = admin.post("/api/sync/tokens", json={"branch_id": other}).json()["token"]
    h2 = {"X-Branch-Id": other, "X-Sync-Token": tok}
    got = admin.get("/api/sync/pull?cursor=0&limit=1", headers=h2).json()
    assert len(got["events"]) == 1 and got["events"][0]["origin_branch_id"] == REMOTE and got["events"][0]["origin_seq"] == 1
    rest = admin.get(f"/api/sync/pull?cursor={got['next_cursor']}", headers=h2).json()
    assert [e["origin_seq"] for e in rest["events"]] == [2]
    assert admin.get(f"/api/sync/pull?cursor={rest['next_cursor']}", headers=h2).json()["events"] == []


class FakeCloud:
    """Stands in for the HTTP link: remembers what was pushed, serves canned changes, can be made to fail."""

    def __init__(self, pull_events=()):
        self.pushed, self.fail, self.pull_events = [], False, list(pull_events)

    def push(self, events):
        if self.fail:
            raise ConnectionError("no internet")
        self.pushed += events
        return {"acked": max((e["seq"] for e in events), default=0), "error": ""}

    def pull(self, cursor):
        if self.fail:
            raise ConnectionError("no internet")
        evs = [e for e in self.pull_events if e["inbox_seq"] > cursor]
        return {"events": evs, "next_cursor": evs[-1]["inbox_seq"] if evs else cursor}


def test_worker_pushes_pulls_keeps_the_cursor_and_survives_outages(admin):
    c = customer(admin)
    base = row(c["id"])
    remote = new_remote(base)
    cloud = FakeCloud([{"inbox_seq": 7, "origin_branch_id": REMOTE, "origin_seq": 1, "table": "customers", "row_id": remote["id"],
                        "op": "upsert", "payload": remote}])
    with SessionLocal() as db:
        branch = db.scalar(select(Branch))
        pending = sync_worker.pending(db)
        assert pending > 0
        cloud.fail = True
        out = sync_worker.run_once(db, branch, cloud)
        assert "no internet" in out["error"] and sync_worker.pending(db) == pending  # nothing lost, nothing marked sent

        cloud.fail = False
        out = sync_worker.run_once(db, branch, cloud)
        assert out == {"pushed": pending, "pulled": 1, "error": ""}
        assert sync_worker.pending(db) == 0 and len(cloud.pushed) == pending
        st = db.get(SyncState, branch.id)
        assert st.pull_cursor == 7 and st.last_error == "" and st.last_push_at and st.last_pull_at
        assert _exists(remote["id"])
        assert sync_worker.pending(db) == 0  # a pulled change is not pushed back out

        assert sync_worker.run_once(db, branch, cloud) == {"pushed": 0, "pulled": 0, "error": ""}  # nothing new, cursor kept
        assert db.get(SyncState, branch.id).pull_cursor == 7


def test_status_page_data_and_manual_run(admin, monkeypatch):
    monkeypatch.delenv("SYNC_CLOUD_URL", raising=False)
    customer(admin)
    s = admin.get("/api/sync/status").json()
    assert s["configured"] is False and s["pending"] > 0 and s["open_conflicts"] == 0 and s["last_error"] == ""
    assert admin.post("/api/sync/run").status_code == 409
