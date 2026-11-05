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
from test_phase3_repairs import approved_quote
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


# --- money in and money out -----------------------------------------------------------------------------

from test_phase3_visits import PNG, upload


def category(admin, name="Rent"):
    return next(c for c in admin.get("/api/expense-categories").json() if c["name"] == name)


def entry(admin, **kw):
    body = {"amount": "1000", "account": "cash", "no_proof_reason": "No slip from the shop", **kw}
    return admin.post("/api/money-entries", json=body)


def test_an_expense_needs_a_category_and_proof_or_a_reason_and_posts_to_the_books(admin):
    rent = category(admin)
    assert entry(admin, kind="expense").status_code == 422  # no category
    assert entry(admin, kind="other_income", category_id=rent["id"]).status_code == 422  # only expenses have one
    assert entry(admin, kind="expense", category_id=rent["id"], no_proof_reason="").status_code == 422  # no proof, no reason
    assert entry(admin, kind="expense", category_id=rent["id"], account="bank").status_code == 422  # a transfer needs its reference
    e = entry(admin, kind="expense", category_id=rent["id"], amount="45000", party="Landlord", account="bank", reference="IBFT-55").json()
    assert e["number"].startswith("EXP-") and e["proof_url"] is None
    assert rows(admin)["6000"] == 45000 and rows(admin)["1020"] == -45000
    lines = admin.get("/api/journal/entries", params={"source_type": "money_entry"}).json()[0]["lines"]
    assert any(l["category"] == "Rent" for l in lines)  # the P&L can split expenses by category

    gone = admin.post(f"/api/money-entries/{e['id']}/void", json={"reason": "Wrong month"}).json()
    assert gone["status"] == "voided" and rows(admin)["6000"] == 0 and rows(admin)["1020"] == 0
    assert admin.post(f"/api/money-entries/{e['id']}/void", json={"reason": "Again"}).status_code == 409
    retired = admin.put(f"/api/expense-categories/{rent['id']}", json={"name": "Rent", "is_active": False, "version": rent["version"]})
    assert entry(admin, kind="expense", category_id=rent["id"]).status_code == 422  # a retired category can't be chosen


def test_other_income_capital_drawings_and_transfers_post_the_right_entries(admin):
    entry(admin, kind="other_income", amount="3000", party="Scrap dealer")
    entry(admin, kind="owner_capital", amount="100000", account="bank", reference="OWN-1")
    entry(admin, kind="drawings", amount="2000")
    b = rows(admin)
    assert b["4900"] == -3000 and b["3000"] == -100000 and b["3100"] == 2000
    assert b["1010"] == 3000 - 2000 and b["1020"] == 100000

    assert entry(admin, kind="transfer", amount="5000", account="bank", to_account="bank", reference="x").status_code == 422
    assert entry(admin, kind="transfer", amount="5000", account="bank").status_code == 422  # no destination
    t = entry(admin, kind="transfer", amount="5000", account="bank", to_account="cash", reference="ATM-1")
    assert t.status_code == 201, t.json()
    b = rows(admin)
    assert b["1010"] == 1000 + 5000 and b["1020"] == 95000  # moved, not earned


def test_money_in_gathers_every_source_with_filters_and_totals(admin):
    visit, item, ro = ready_repair(admin)  # a 4000 cash advance, taken without proof
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    inv = admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}).json()
    admin.post(f"/api/invoices/{inv['id']}/payments", json={"amount": "2000", "account": "bank", "reference": "IBFT-9", "proof_id": upload(admin, PNG + b"s")})
    entry(admin, kind="other_income", amount="750", party="Scrap dealer")
    entry(admin, kind="transfer", amount="500", account="bank", to_account="cash", reference="ATM")

    page = admin.get("/api/money-in").json()
    assert {r["source"] for r in page["rows"]} == {"advance", "invoice_payment", "other_income", "transfer"}
    assert D(str(page["total"])) == 4000 + 2000 + 750  # the transfer isn't income
    assert D(str(page["by_account"]["cash"])) == 4000 + 750 + 500 and D(str(page["by_account"]["bank"])) == 2000
    assert page["missing_proof"] == 3  # the advance, the other income and the transfer have a reason but no proof
    only = admin.get("/api/money-in", params={"missing_proof": True, "account": "cash"}).json()
    assert {r["source"] for r in only["rows"]} == {"advance", "other_income", "transfer"}
    assert [r["source"] for r in admin.get("/api/money-in", params={"source": "invoice_payment"}).json()["rows"]] == ["invoice_payment"]
    assert [r["party"] for r in admin.get("/api/money-in", params={"q": "scrap"}).json()["rows"]] == ["Scrap dealer"]
    assert admin.get("/api/money-in", params={"date_from": (date.today() + timedelta(days=1)).isoformat()}).json()["rows"] == []
    assert D(str(admin.get("/api/money-in", params={"date_to": date.today().isoformat()}).json()["total"])) == D(str(page["total"]))


def test_money_out_gathers_vendor_payments_expenses_and_transfers_once_each(admin):
    vendor, item, po = sent_po(admin)
    grn = receive(admin, po, "10").json()["receipts"][0]
    bill = admin.post(f"/api/goods-receipts/{grn['id']}/bill", json={"bill_date": date.today().isoformat()}).json()
    admin.post(f"/api/bills/{bill['id']}/payments", json={"amount": "1500", **CASH})
    entry(admin, kind="expense", category_id=category(admin, "Tea and refreshments")["id"], amount="300")
    entry(admin, kind="transfer", amount="900", account="cash", to_account="bank", reference="DEP-1")
    out = admin.get("/api/money-out").json()
    assert sorted(r["source"] for r in out["rows"]) == ["expense", "transfer", "vendor_payment"]
    assert D(str(out["total"])) == 1500 + 300
    assert D(str(out["by_account"]["cash"])) == 1500 + 300 + 900
    assert [r["party"] for r in admin.get("/api/money-out", params={"source": "vendor_payment"}).json()["rows"]] == [vendor["name"]]
    assert rows(admin)["1010"] == -(1500 + 300 + 900)


def test_who_may_record_what(admin):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    for name, role in (("inv", "Inventory manager"), ("acct", "Accountant")):
        admin.post("/api/users", json={"username": name, "full_name": name, "password": f"{name}-pass-1234", "role_id": roles[role], "branch_ids": [branch_id]})
    inv, acct = signed_in("inv", "inv-pass-1234"), signed_in("acct", "acct-pass-1234")
    tea = category(admin, "Tea and refreshments")["id"]
    assert entry(inv, kind="expense", category_id=tea).status_code == 403
    assert inv.get("/api/money-out").status_code == 403
    assert entry(acct, kind="expense", category_id=tea).status_code == 201  # the accountant records expenses
    assert entry(acct, kind="other_income").status_code == 403  # but money in needs payments-in
    assert acct.get("/api/money-in").status_code == 200


# --- credit notes and refunds -----------------------------------------------------------------------------

def issued_invoice(admin):
    visit, item, ro = ready_repair(admin)  # labour 3000 + 2 filters at 3000, 17% tax = 10530; 4000 advance
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    return item, admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}).json()


def test_a_credit_note_reverses_revenue_tax_and_receivable_and_restocks_at_cost(admin):
    item, inv = issued_invoice(admin)  # receivable 6530 after the advance
    part = next(l for l in inv["lines"] if l["kind"] == "part")
    stock_before = D(str(admin.get(f"/api/items/{item['id']}").json()["on_hand"]))
    r = admin.post(f"/api/invoices/{inv['id']}/credit-notes", json={"reason": "One filter was wrong", "lines": [{"invoice_line_id": part["id"], "qty": "1", "restock": True}]})
    assert r.status_code == 201, r.json()
    cn = r.json()["credit_notes"][0]
    assert cn["number"].startswith("CN-") and D(str(cn["total"])) == D("3510.00")  # 3000 + 17%
    assert D(str(admin.get(f"/api/items/{item['id']}").json()["on_hand"])) == stock_before + 1  # back on the shelf
    b = rows(admin)
    assert b["4100"] == -3000 and b["2300"] == D("-1020") and b["1100"] == D("6530") - D("3510")  # half the parts revenue reversed
    assert b["5000"] == 1000 and b["1200"] == stock_value()  # one filter's cost came back at its original cost
    now = admin.get(f"/api/invoices/{inv['id']}").json()
    assert D(str(now["totals"]["credited"])) == D("3510.00") and D(str(now["totals"]["balance"])) == D("3020.00")


def test_credit_note_limits_and_the_one_time_return_of_a_line(admin):
    item, inv = issued_invoice(admin)
    part = next(l for l in inv["lines"] if l["kind"] == "part")
    labour = next(l for l in inv["lines"] if l["kind"] == "labour")
    url = f"/api/invoices/{inv['id']}/credit-notes"
    assert admin.post(url, json={"reason": "x", "lines": [{"invoice_line_id": part["id"], "qty": "1"}]}).status_code == 422  # a reason
    assert admin.post(url, json={"reason": "Too many", "lines": [{"invoice_line_id": part["id"], "qty": "3"}]}).status_code == 422
    assert admin.post(url, json={"reason": "Labour back", "lines": [{"invoice_line_id": labour["id"], "qty": "1", "restock": True}]}).status_code == 422
    assert admin.post(url, json={"reason": "Both", "lines": [{"invoice_line_id": part["id"], "qty": "2"}]}).status_code == 201
    assert admin.post(url, json={"reason": "Again", "lines": [{"invoice_line_id": part["id"], "qty": "1"}]}).status_code == 422  # nothing left to credit


def test_overpayment_after_a_credit_note_is_refunded_through_money_out(admin):
    item, inv = issued_invoice(admin)
    admin.post(f"/api/invoices/{inv['id']}/payments", json={"amount": "6530", **CASH})  # paid in full
    part = next(l for l in inv["lines"] if l["kind"] == "part")
    after = admin.post(f"/api/invoices/{inv['id']}/credit-notes", json={"reason": "Both filters back", "lines": [{"invoice_line_id": part["id"], "qty": "2", "restock": True}]}).json()
    assert D(str(after["totals"]["balance"])) == -D("7020.00")  # overpaid by exactly what was credited
    due = D(str(after["totals"]["refundable"]))
    assert due == D("7020.00")  # credited 2 x 3000 + 17%, all of it already paid
    assert admin.post(f"/api/invoices/{inv['id']}/refund", json={"amount": str(due + 1), **CASH}).status_code == 422
    assert admin.post(f"/api/invoices/{inv['id']}/refund", json={"amount": "7020", "account": "cash"}).status_code == 422  # proof or reason
    done = admin.post(f"/api/invoices/{inv['id']}/refund", json={"amount": "7020", **CASH})
    assert done.status_code == 201, done.json()
    assert D(str(done.json()["totals"]["refundable"])) == 0 and D(str(done.json()["totals"]["balance"])) == 0
    out = admin.get("/api/money-out").json()
    assert [r["source"] for r in out["rows"]] == ["refund"] and D(str(out["total"])) == 7020
    b = rows(admin)
    assert b["1100"] == 0 and b["1010"] == 4000 + 6530 - 7020  # cash in, less the refund


def test_a_held_advance_is_refunded_in_full_by_an_admin_only(admin):
    visit, item, _, q = approved_quote(admin)
    advance = admin.post(f"/api/quotations/{q['id']}/advances", json={"amount": "2500", **CASH}).json()
    adv_id = advance["id"]
    assert admin.post(f"/api/advances/{adv_id}/refund", json={"amount": "3000", "reason": "Job cancelled", **CASH}).status_code == 422  # more than held
    assert admin.post(f"/api/advances/{adv_id}/refund", json={"amount": "2500", "reason": "x", **CASH}).status_code == 422  # a reason
    assert admin.post(f"/api/visits/{visit['id']}/cancel", json={"reason": "Customer left"}).status_code == 409  # money is held
    done = admin.post(f"/api/advances/{adv_id}/refund", json={"amount": "2500", "reason": "Job cancelled", **CASH})
    assert done.status_code == 201 and done.json()["refunded"] is True
    assert admin.post(f"/api/advances/{adv_id}/refund", json={"amount": "2500", "reason": "Again", **CASH}).status_code == 409
    b = rows(admin)
    assert b["2200"] == 0 and b["1010"] == 0  # the liability is cleared and the cash is back out
    assert admin.post(f"/api/visits/{visit['id']}/cancel", json={"reason": "Customer left"}).status_code == 200  # nothing held any more
    refund_entry = next(r for r in admin.get("/api/money-out").json()["rows"] if r["source"] == "refund")
    voided = admin.post(f"/api/money-entries/{refund_entry['entry_id']}/void", json={"reason": "Wrong amount recorded"}).json()
    assert voided["status"] == "voided"
    assert rows(admin)["2200"] == -2500  # the advance is held again

    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    admin.post("/api/users", json={"username": "acct", "full_name": "Acct", "password": "acct-pass-1234", "role_id": roles["Accountant"], "branch_ids": [branch_id]})
    assert signed_in("acct", "acct-pass-1234").post(f"/api/advances/{adv_id}/refund", json={"amount": "2500", "reason": "x" * 5, **CASH}).status_code == 403


def test_a_held_advance_can_be_given_back_in_parts(admin):
    visit, item, _, q = approved_quote(admin)
    adv_id = admin.post(f"/api/quotations/{q['id']}/advances", json={"amount": "2500", **CASH}).json()["id"]
    part = admin.post(f"/api/advances/{adv_id}/refund", json={"amount": "1000", "reason": "Customer changed the work", **CASH})
    assert part.status_code == 201 and part.json()["refunded"] is False and float(part.json()["held"]) == 1500
    assert rows(admin)["2200"] == -1500
    assert admin.post(f"/api/advances/{adv_id}/refund", json={"amount": "1600", "reason": "Too much", **CASH}).status_code == 422
    rest = admin.post(f"/api/advances/{adv_id}/refund", json={"amount": "1500", "reason": "The rest", **CASH})
    assert rest.status_code == 201 and rest.json()["refunded"] is True and rows(admin)["2200"] == 0


def test_a_counter_sale_return_puts_the_part_back_at_its_cost(admin):
    from test_phase2 import new_item
    item = new_item(admin, name="Headlight", codes=(("mpn", "63117440"),), opening_qty="3", opening_cost="20000")
    cs = admin.post("/api/counter-sales", json={"lines": [{"kind": "part", "item_id": item["id"], "qty": "1", "unit_price": "30000"}], "include_tax": False}).json()
    cs = admin.post(f"/api/invoices/{cs['id']}/issue", json={"version": cs["version"], "payments": [{"amount": "30000", **CASH}]}).json()
    back = admin.post(f"/api/invoices/{cs['id']}/credit-notes", json={"reason": "Wrong model", "lines": [{"invoice_line_id": cs["lines"][0]["id"], "qty": "1", "restock": True}]}).json()
    assert D(str(back["totals"]["refundable"])) == 30000
    b = rows(admin)
    assert b["5000"] == 0 and b["4100"] == 0 and b["1200"] == 60000 == stock_value()  # 3 headlights at 20000 again
    admin.post(f"/api/invoices/{cs['id']}/refund", json={"amount": "30000", **CASH})
    assert rows(admin)["1010"] == 0


# --- daily cash close ------------------------------------------------------------------------------------

def test_closing_a_day_signs_the_count_and_posts_the_difference(admin):
    cash = next(a for a in admin.get("/api/accounts").json() if a["kind"] == "cash")
    admin.put(f"/api/accounts/{cash['id']}", json={"name": cash["name"], "opening_balance": "10000", "opening_date": date.today().isoformat(), "version": cash["version"]})
    entry(admin, kind="other_income", amount="2500")
    st = next(s for s in admin.get("/api/cash-closes/status").json() if s["account"] == "cash")
    assert D(str(st["expected"])) == 12500 and st["last_close"] is None and not st["closed_today"]
    assert st["next_close_date"] == date.today().isoformat() and st["may_close_earlier"] is True and st["days_behind"] == 0

    assert admin.post("/api/cash-closes", json={"account": "cash", "counted": "12300"}).status_code == 422  # short without a reason
    done = admin.post("/api/cash-closes", json={"account": "cash", "counted": "12300", "reason": "Change given wrongly to a customer"})
    assert done.status_code == 201, done.json()
    c = done.json()
    assert (D(str(c["expected"])), D(str(c["counted"])), D(str(c["difference"]))) == (12500, 12300, -200) and c["closed_by"] == "Administrator"
    b = rows(admin)
    assert b["1010"] == 12300 and b["6910"] == 200  # the books now say what was counted; the shortage is an expense
    assert admin.post("/api/cash-closes", json={"account": "cash", "counted": "12300"}).status_code == 409  # once a day
    done_st = next(s for s in admin.get("/api/cash-closes/status").json() if s["account"] == "cash")
    assert done_st["closed_today"] is True and done_st["next_close_date"] is None
    assert admin.get("/api/cash-closes", params={"account": "cash"}).json()[0]["difference"] == -200


def test_a_missed_day_is_closed_before_today_with_its_own_books(admin):
    """Yesterday and today each get their own signed count; today's books include today's takings only after yesterday is signed."""
    yesterday = date.today() - timedelta(days=1)
    entry(admin, kind="other_income", amount="100", occurred_on=yesterday.isoformat())
    entry(admin, kind="other_income", amount="40")
    exp_y = admin.get("/api/cash-closes/expected", params={"account": "cash", "on": yesterday.isoformat()})
    assert exp_y.status_code == 200 and D(str(exp_y.json()["expected"])) == 100
    assert admin.post("/api/cash-closes", json={"account": "cash", "close_date": yesterday.isoformat(), "counted": "100"}).status_code == 201
    st = next(s for s in admin.get("/api/cash-closes/status").json() if s["account"] == "cash")
    assert st["next_close_date"] == date.today().isoformat() and st["days_behind"] == 0 and not st["closed_today"]
    assert D(str(st["expected_on_next"])) == 140
    assert admin.post("/api/cash-closes", json={"account": "cash", "counted": "140"}).status_code == 201
    assert next(s for s in admin.get("/api/cash-closes/status").json() if s["account"] == "cash")["closed_today"] is True


def test_status_shows_days_behind_when_a_day_was_skipped(admin):
    two_ago = date.today() - timedelta(days=2)
    entry(admin, kind="other_income", amount="10", occurred_on=two_ago.isoformat())
    assert admin.post("/api/cash-closes", json={"account": "cash", "close_date": two_ago.isoformat(), "counted": "10"}).status_code == 201
    st = next(s for s in admin.get("/api/cash-closes/status").json() if s["account"] == "cash")
    assert st["next_close_date"] == (date.today() - timedelta(days=1)).isoformat() and st["days_behind"] == 1


def test_a_surplus_is_income_and_an_exact_count_posts_nothing(admin):
    entry(admin, kind="other_income", amount="1000", account="wallet", reference="JC-1")
    done = admin.post("/api/cash-closes", json={"account": "wallet", "counted": "1000"})
    assert done.status_code == 201 and D(str(done.json()["difference"])) == 0
    assert not admin.get("/api/journal/entries", params={"source_type": "cash_close"}).json()
    entry(admin, kind="other_income", amount="500")
    over = admin.post("/api/cash-closes", json={"account": "cash", "counted": "560", "reason": "Customer left a tip"}).json()
    assert D(str(over["difference"])) == 60 and rows(admin)["6910"] == -60 and rows(admin)["1010"] == 560


def test_a_closed_day_is_locked_and_days_close_in_order(admin):
    entry(admin, kind="other_income", amount="100")
    assert admin.post("/api/cash-closes", json={"account": "cash", "counted": "100"}).status_code == 201
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert entry(admin, kind="other_income", amount="50", occurred_on=yesterday).status_code == 409  # backdating into a closed day
    assert admin.post("/api/cash-closes", json={"account": "cash", "counted": "100", "close_date": yesterday}).status_code == 409  # out of order
    future = (date.today() + timedelta(days=1)).isoformat()
    assert admin.post("/api/cash-closes", json={"account": "bank", "counted": "0", "close_date": future}).status_code == 422
    first = next(r for r in admin.get("/api/money-in").json()["rows"] if r["source"] == "other_income")
    assert admin.post(f"/api/money-entries/{first['entry_id']}/void", json={"reason": "Mistake"}).status_code == 409  # voiding into a closed day


def test_only_cash_close_users_sign_counts(admin):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    for name, role in (("inv", "Inventory manager"), ("acct", "Accountant")):
        admin.post("/api/users", json={"username": name, "full_name": name, "password": f"{name}-pass-1234", "role_id": roles[role], "branch_ids": [branch_id]})
    assert signed_in("inv", "inv-pass-1234").get("/api/cash-closes/status").status_code == 403
    acct = signed_in("acct", "acct-pass-1234")
    assert acct.post("/api/cash-closes", json={"account": "bank", "counted": "0"}).status_code == 201


# --- missing evidence ---------------------------------------------------------------------------------------

def test_missing_evidence_lists_every_record_without_proof_and_an_admin_signs_it_off(admin):
    visit, item, ro = ready_repair(admin)  # the advance has a reason, not a photo
    entry(admin, kind="other_income", amount="750", party="Scrap dealer")
    entry(admin, kind="transfer", amount="100", account="bank", to_account="cash", reference="ATM")
    with_proof = entry(admin, kind="other_income", amount="60", proof_id=upload(admin, PNG + b"x"), no_proof_reason="").json()
    assert with_proof["proof_url"]

    page = admin.get("/api/missing-evidence").json()
    assert page["open"] == 3 and D(str(page["open_total"])) == 4000 + 750 + 100  # the transfer shows once, not twice
    assert {r["source"] for r in page["rows"]} == {"advance", "other_income", "transfer"}
    money_in = admin.get("/api/money-in").json()
    assert money_in["missing_proof"] == 3

    target = next(r for r in page["rows"] if r["source"] == "other_income")
    body = {"source_type": target["source_type"], "source_id": target["id"]}
    assert admin.post("/api/missing-evidence/sign", json={**body, "reason": "x"}).status_code == 422
    assert admin.post("/api/missing-evidence/sign", json={**body, "reason": "Small cash sale, no slip given"}).status_code == 201
    assert admin.post("/api/missing-evidence/sign", json={**body, "reason": "Again and again"}).status_code == 409
    after = admin.get("/api/missing-evidence").json()
    assert after["open"] == 2 and after["signed_off"] == 1
    assert admin.get("/api/money-in").json()["missing_proof"] == 2  # the sign-off clears the alert count
    both = admin.get("/api/missing-evidence", params={"include_signed": True}).json()
    signed = next(r for r in both["rows"] if r["id"] == target["id"])
    assert signed["signoff"]["reason"] == "Small cash sale, no slip given" and signed["signoff"]["by"] == "Administrator"
    ok = next(r for r in admin.get("/api/money-in").json()["rows"] if r["id"] == with_proof["id"])
    assert admin.post("/api/missing-evidence/sign", json={"source_type": "money_entry", "source_id": ok["id"], "reason": "Not needed here"}).status_code == 409  # it has proof


def test_only_admins_with_the_permission_sign_off(admin):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    admin.post("/api/users", json={"username": "acct", "full_name": "Acct", "password": "acct-pass-1234", "role_id": roles["Accountant"], "branch_ids": [branch_id]})
    e = entry(admin, kind="other_income", amount="10").json()
    acct = signed_in("acct", "acct-pass-1234")
    assert acct.get("/api/missing-evidence").status_code == 200
    assert acct.post("/api/missing-evidence/sign", json={"source_type": "money_entry", "source_id": e["id"], "reason": "Not allowed to do this"}).status_code == 403


def test_money_records_accept_several_proof_files(admin):
    a = upload(admin, PNG + b"one")
    b = upload(admin, PNG + b"two")
    e = entry(admin, kind="other_income", amount="90", party="Scrap", proof_ids=[a, b], no_proof_reason="").json()
    assert e["proof_url"] and len(e["proof_urls"]) == 2
    listed = next(r for r in admin.get("/api/money-in").json()["rows"] if r["id"] == e["id"])
    assert listed["proof_urls"] == e["proof_urls"]

    later = entry(admin, kind="other_income", amount="12", party="Cash tip").json()
    c, d = upload(admin, PNG + b"c"), upload(admin, PNG + b"d")
    attached = admin.post("/api/missing-evidence/attach", json={
        "source_type": "money_entry", "source_id": later["id"], "proof_ids": [c, d],
    }).json()
    assert len(attached["proof_urls"]) == 2


def test_missing_evidence_can_optionally_attach_proof_later(admin):
    e = entry(admin, kind="other_income", amount="80", party="Scrap").json()
    before = admin.get("/api/missing-evidence").json()
    assert any(r["id"] == e["id"] for r in before["rows"])
    open_before = before["open"]

    assert admin.post("/api/missing-evidence/attach", json={
        "source_type": "money_entry", "source_id": e["id"],
    }).status_code == 422  # proof is only needed when you choose to attach it

    ok = admin.post("/api/missing-evidence/attach", json={
        "source_type": "money_entry", "source_id": e["id"], "proof_id": upload(admin, PNG + b"later"),
    })
    assert ok.status_code == 200 and ok.json()["proof_url"]
    after = admin.get("/api/missing-evidence").json()
    assert after["open"] == open_before - 1
    assert not any(r["id"] == e["id"] for r in after["rows"])
    assert admin.post("/api/missing-evidence/attach", json={
        "source_type": "money_entry", "source_id": e["id"], "proof_id": upload(admin, PNG + b"again"),
    }).status_code == 409  # already has proof
    # Accept without proof still works for other records — attaching later is optional
    other = entry(admin, kind="other_income", amount="15").json()
    assert admin.post("/api/missing-evidence/sign", json={
        "source_type": "money_entry", "source_id": other["id"], "reason": "Small cash, no slip expected",
    }).status_code == 201
