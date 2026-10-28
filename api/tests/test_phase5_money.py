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


# --- the journal follows the documents ---------------------------------------------------------------

from sqlalchemy import func

from app.models import StockMovement
from test_phase3_billing import CASH, ready_repair
from test_phase4_purchasing import receive, sent_po


def rows(admin):
    tb = admin.get("/api/journal/trial-balance").json()
    assert tb["balanced"], tb
    return {r["code"]: D(str(r["balance"])) for r in tb["rows"]}


def stock_value():
    with SessionLocal() as db:
        return db.scalar(select(func.coalesce(func.sum(StockMovement.qty * StockMovement.unit_cost), 0)))


def test_a_workshop_job_posts_revenue_receivable_and_cost(admin):
    visit, item, ro = ready_repair(admin)  # 4000 advance already held
    b = rows(admin)
    assert b["2200"] == -4000 and b["1010"] == 4000 and b["1200"] == 6000 - 2000  # advance held; 2 of 6 filters issued
    assert b["5000"] == 2000  # cost of the parts issued, at cost
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    inv = admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}).json()
    b = rows(admin)
    assert b["4000"] == -3000 and b["4100"] == -6000 and b["2300"] == -1530  # revenue and tax
    assert b["1100"] == D("6530") and b["2200"] == 0  # the advance settled part of the receivable
    admin.post(f"/api/invoices/{inv['id']}/payments", json={"amount": "6530", **CASH})
    b = rows(admin)
    assert b["1100"] == 0 and b["1010"] == D("10530")
    assert b["1200"] == stock_value()  # the books' inventory equals the stock ledger


def test_returning_a_part_and_the_discount_split(admin):
    visit, item, ro = ready_repair(admin)
    part = next(l for l in ro["lines"] if l["kind"] == "part")
    admin.post(f"/api/repair-orders/{ro['id']}/lines/{part['id']}/return", json={"qty": "1"})
    assert rows(admin)["5000"] == 1000  # one came back, so only one filter was consumed
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    inv = admin.put(f"/api/invoices/{inv['id']}", json={"prices": {}, "include_tax": False, "discount": "300", "version": inv["version"]}).json()
    inv = admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}).json()
    b = rows(admin)  # labour 3000 + one filter 3000, less 300 shared in proportion: 150 off each
    assert b["4000"] == -2850 and b["4100"] == -2850 and b["2300"] == 0 and b["1100"] == D("5700") - 4000  # total 5700, less the advance already held


def test_purchases_post_stock_payable_and_freight(admin):
    vendor, item, po = sent_po(admin)  # 10 in stock at 100
    grn = receive(admin, po, "10").json()["receipts"][0]  # 10 x 200
    b = rows(admin)
    assert b["1200"] == 1000 + 2000 and b["2100"] == -2000  # received but not billed yet
    bill = admin.post(f"/api/goods-receipts/{grn['id']}/bill", json={"bill_date": date.today().isoformat(), "adjustment": "150", "adjustment_reason": "Freight"}).json()
    b = rows(admin)
    assert b["2100"] == 0 and b["2000"] == -2150 and b["6200"] == 150
    pay = admin.post(f"/api/bills/{bill['id']}/payments", json={"amount": "1000", **CASH}).json()["payments"][0]
    b = rows(admin)
    assert b["2000"] == -1150 and b["1010"] == -1000
    admin.post(f"/api/vendor-payments/{pay['id']}/void", json={"reason": "Entered twice"})
    assert rows(admin)["2000"] == -2150 and rows(admin)["1010"] == 0  # the payment reversed
    admin.post(f"/api/bills/{bill['id']}/void", json={"reason": "Wrong vendor"})
    b = rows(admin)
    assert b["2000"] == 0 and b["6200"] == 0 and b["2100"] == -2000  # unbilled again, and still in stock
    assert b["1200"] == stock_value()


def test_counter_sale_posts_revenue_cost_and_cash(admin):
    from test_phase2 import new_item
    item = new_item(admin, name="Headlight", codes=(("mpn", "63117440"),), opening_qty="3", opening_cost="20000")
    line = {"kind": "part", "item_id": item["id"], "qty": "1", "unit_price": "30000"}
    cs = admin.post("/api/counter-sales", json={"lines": [line], "include_tax": False}).json()
    admin.post(f"/api/invoices/{cs['id']}/issue", json={"version": cs["version"], "payments": [{"amount": "30000", **CASH}]})
    b = rows(admin)
    assert b["4100"] == -30000 and b["1010"] == 30000 and b["1100"] == 0 and b["5000"] == 20000
    assert b["1200"] == 40000 and b["1200"] == stock_value()


def test_stock_adjustments_hit_the_books(admin):
    from test_phase2 import new_item
    item = new_item(admin, name="Wiper", codes=(("barcode", "9900001"),), opening_qty="10", opening_cost="100")
    assert rows(admin)["1200"] == 1000 and rows(admin)["3900"] == -1000  # opening stock against opening equity
    admin.post(f"/api/items/{item['id']}/adjust", json={"qty": "-2", "reason": "Damaged on the shelf"})
    b = rows(admin)
    assert b["1200"] == 800 and b["6900"] == 200
