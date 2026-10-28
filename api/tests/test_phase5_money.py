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
