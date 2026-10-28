from datetime import date, timedelta
from decimal import Decimal

from test_foundation import signed_in

D = Decimal


def test_every_branch_gets_three_accounts_and_default_categories(admin):
    accounts = admin.get("/api/accounts").json()
    assert [a["kind"] for a in accounts] == ["bank", "cash", "wallet"]
    assert all(D(str(a["opening_balance"])) == 0 for a in accounts)
    assert admin.get("/api/accounts").json() == accounts  # asking again creates nothing new
    names = [c["name"] for c in admin.get("/api/expense-categories").json()]
    assert "Rent" in names and len(names) == len(set(names)) >= 10


def test_opening_balance_is_edited_with_a_version_check(admin):
    cash = next(a for a in admin.get("/api/accounts").json() if a["kind"] == "cash")
    body = {"name": "Cash drawer", "opening_balance": "25000", "opening_date": date.today().isoformat(), "version": cash["version"]}
    done = admin.put(f"/api/accounts/{cash['id']}", json=body)
    assert done.status_code == 200 and done.json()["name"] == "Cash drawer"
    assert admin.put(f"/api/accounts/{cash['id']}", json=body).status_code == 409  # stale version
    future = {**body, "opening_date": (date.today() + timedelta(days=1)).isoformat(), "version": done.json()["version"]}
    assert admin.put(f"/api/accounts/{cash['id']}", json=future).status_code == 422
    assert admin.put(f"/api/accounts/{cash['id']}", json={**future, "opening_date": date.today().isoformat(), "opening_balance": "-5"}).status_code == 422


def test_categories_are_unique_and_can_be_retired(admin):
    admin.get("/api/expense-categories")
    made = admin.post("/api/expense-categories", json={"name": "Garbage collection"})
    assert made.status_code == 201
    assert admin.post("/api/expense-categories", json={"name": "garbage COLLECTION"}).status_code == 409
    c = made.json()
    gone = admin.put(f"/api/expense-categories/{c['id']}", json={"name": "Garbage collection", "is_active": False, "version": c["version"]})
    assert gone.status_code == 200
    assert "Garbage collection" not in [x["name"] for x in admin.get("/api/expense-categories").json()]
    assert "Garbage collection" in [x["name"] for x in admin.get("/api/expense-categories", params={"include_inactive": True}).json()]


def test_only_settings_users_change_money_setup(admin):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    admin.post("/api/users", json={"username": "acct", "full_name": "Acct", "password": "acct-pass-123", "role_id": roles["Accountant"], "branch_ids": [branch_id]})
    acct = signed_in("acct", "acct-pass-123")
    assert acct.get("/api/accounts").status_code == 200  # the accountant can see them
    assert acct.post("/api/expense-categories", json={"name": "Anything"}).status_code == 403


# --- the journal ---------------------------------------------------------------------------------

import pytest
from sqlalchemy import select

from app import journal
from app.db import SessionLocal
from app.models import Branch
from app.journal import JournalError, Line


def test_post_refuses_unbalanced_and_one_sided_entries(admin):
    with SessionLocal() as db:
        branch = db.scalar(select(Branch))
        with pytest.raises(JournalError, match="Unbalanced"):
            journal.post(db, branch, "bad", [Line("1010", debit=D("100")), Line("4000", credit=D("90"))])
        with pytest.raises(JournalError, match="at least two"):
            journal.post(db, branch, "bad", [Line("1010", debit=D("100"))])
        with pytest.raises(JournalError, match="either a debit or a credit"):
            journal.post(db, branch, "bad", [Line("1010", debit=D("100"), credit=D("100")), Line("4000", credit=D("1"))])
        with pytest.raises(JournalError, match="Unknown"):
            journal.post(db, branch, "bad", [Line("9999", debit=D("5")), Line("4000", credit=D("5"))])
        assert journal.post(db, branch, "nothing", [Line("1010"), Line("4000")]) is None  # all zeros posts nothing
        db.rollback()


def test_reversal_mirrors_once_and_cancels_the_balance(admin):
    with SessionLocal() as db:
        branch = db.scalar(select(Branch))
        e = journal.post(db, branch, "sale", [Line("1010", debit=D("500.50")), Line("4000", credit=D("500.50"))], source=("test", __import__("uuid").uuid4()))
        assert journal.money_balance(db, branch, "cash") == D("500.50")
        r = journal.reverse(db, branch, e, "undo")
        assert r.reverses_id == e.id and journal.money_balance(db, branch, "cash") == 0
        with pytest.raises(JournalError, match="already been reversed"):
            journal.reverse(db, branch, e, "again")
        assert journal.live_entry(db, "test", e.source_id) is None  # a reversed entry is no longer live
        db.rollback()


def test_opening_balances_post_to_the_journal_and_the_trial_balance_balances(admin):
    cash = next(a for a in admin.get("/api/accounts").json() if a["kind"] == "cash")
    body = {"name": cash["name"], "opening_balance": "25000", "opening_date": date.today().isoformat(), "version": cash["version"]}
    done = admin.put(f"/api/accounts/{cash['id']}", json=body).json()
    assert D(str(done["balance"])) == 25000
    again = admin.put(f"/api/accounts/{cash['id']}", json={**body, "opening_balance": "30000", "version": done["version"]}).json()
    assert D(str(again["balance"])) == 30000  # corrected through a reversal, not an edit

    tb = admin.get("/api/journal/trial-balance").json()
    rows = {r["code"]: r for r in tb["rows"]}
    assert tb["balanced"] and D(str(rows["1010"]["balance"])) == 30000 and D(str(rows["3900"]["balance"])) == -30000
    entries = admin.get("/api/journal/entries", params={"source_type": "account_opening"}).json()
    assert len(entries) == 3 and sum(1 for e in entries if e["reverses_id"]) == 1  # opening, its reversal, the corrected opening
    assert [a["balance"] for a in admin.get("/api/accounts").json() if a["kind"] == "cash"] == [30000]


def test_the_journal_is_for_finance_users_only(admin):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    admin.post("/api/users", json={"username": "inv", "full_name": "Inv", "password": "inv-pass-1234", "role_id": roles["Inventory manager"], "branch_ids": [branch_id]})
    assert signed_in("inv", "inv-pass-1234").get("/api/journal/trial-balance").status_code == 403
