import uuid

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import ExpenseCategory


def count(name):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(ExpenseCategory).where(ExpenseCategory.name == name))


def test_the_same_key_does_it_once_and_replays_the_answer(admin):
    key = {"Idempotency-Key": str(uuid.uuid4())}
    first = admin.post("/api/expense-categories", json={"name": "Garbage collection"}, headers=key)
    again = admin.post("/api/expense-categories", json={"name": "Garbage collection"}, headers=key)
    assert first.status_code == 201 and again.status_code == 201
    assert again.json() == first.json() and again.headers["idempotency-replayed"] == "true"
    assert "idempotency-replayed" not in first.headers
    assert count("Garbage collection") == 1
    # Without a key the second attempt really is a second attempt, and is refused as a duplicate.
    assert admin.post("/api/expense-categories", json={"name": "Garbage collection"}).status_code in (409, 422)


def test_a_key_cannot_be_reused_for_a_different_request(admin):
    key = {"Idempotency-Key": str(uuid.uuid4())}
    assert admin.post("/api/expense-categories", json={"name": "Tea and biscuits"}, headers=key).status_code == 201
    other = admin.post("/api/expense-categories", json={"name": "Something else"}, headers=key)
    assert other.status_code == 422 and "different request" in other.json()["detail"]
    assert count("Something else") == 0


def test_a_failed_attempt_does_not_use_up_the_key(admin):
    key = {"Idempotency-Key": str(uuid.uuid4())}
    assert admin.post("/api/expense-categories", json={"name": ""}, headers=key).status_code == 422  # invalid: nothing kept
    assert admin.post("/api/expense-categories", json={"name": ""}, headers=key).status_code == 422  # same answer, not "mismatch"/"busy"


def test_keys_do_not_cross_between_people(admin):
    from test_foundation import signed_in
    key = {"Idempotency-Key": "shared-by-accident"}
    assert admin.post("/api/expense-categories", json={"name": "Mine"}, headers=key).status_code == 201
    roles = admin.get("/api/roles").json()
    admin.post("/api/users", json={"username": "second", "full_name": "Second", "password": "second-pass-123",
                                   "role_id": next(r["id"] for r in roles if r["name"] == "Admin"),
                                   "branch_ids": [admin.get("/api/auth/me").json()["branch"]["id"]]})
    other = signed_in("second", "second-pass-123")
    got = other.post("/api/expense-categories", json={"name": "Theirs"}, headers=key)
    assert got.status_code == 201 and got.json()["name"] == "Theirs"  # not the first person's replayed answer
