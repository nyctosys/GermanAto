from datetime import date, timedelta
from decimal import Decimal

from test_foundation import signed_in
from test_phase3_billing import CASH, ready_repair
from test_phase4_purchasing import receive, sent_po
from test_phase5_money import category, entry, rows
from test_phase6_hr import staff

D = Decimal
SEP15, SEP20 = "2026-09-15", "2026-09-20"


def users(admin):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    for name, role in (("acct", "Accountant"), ("inv", "Inventory manager")):
        admin.post("/api/users", json={"username": name, "full_name": name, "password": f"{name}-pass-1234", "role_id": roles[role], "branch_ids": [branch_id]})
    return signed_in("acct", "acct-pass-1234"), signed_in("inv", "inv-pass-1234")


def september(admin):
    """1000 other income and 300 of tea in September, each with only a reason."""
    entry(admin, kind="other_income", amount="1000", occurred_on=SEP15)
    tea = entry(admin, kind="expense", category_id=category(admin, "Tea and refreshments")["id"], amount="300", occurred_on=SEP20).json()
    return tea


def ready_to_close(admin, seed=True):
    if seed:
        september(admin)
    for r in admin.get("/api/missing-evidence").json()["rows"]:
        admin.post("/api/missing-evidence/sign", json={"source_type": r["source_type"], "source_id": r["id"], "reason": "Small cash items, no slips"})
    assert admin.post("/api/cash-closes", json={"account": "cash", "close_date": "2026-09-30", "counted": "700"}).status_code == 201


def test_a_month_closes_only_when_its_checklist_is_complete_and_then_it_is_locked(admin):
    september(admin)
    cl = admin.get("/api/periods/2026-09/checklist").json()
    todo = {i["key"] for i in cl["items"] if i["blocking"] and not i["ok"]}
    assert todo == {"proof", "cash_cash"} and not cl["can_close"]
    assert admin.post("/api/periods/2026-09/close", json={}).status_code == 409  # not ready

    ready_to_close(admin, seed=False)  # September's entries are already there
    cl = admin.get("/api/periods/2026-09/checklist").json()
    assert cl["can_close"] and cl["blockers"] == 0
    closed = admin.post("/api/periods/2026-09/close", json={"notes": "All checked"}).json()
    assert closed["status"] == "closed" and closed["closed_by"] == "Administrator"
    assert admin.post("/api/periods/2026-09/close", json={}).status_code == 409  # already

    late = entry(admin, kind="other_income", amount="50", account="wallet", reference="JC-9", occurred_on="2026-09-25")
    assert late.status_code == 409 and "September 2026" in late.json()["detail"]  # a day inside a closed month (the wallet has no signed count)
    assert entry(admin, kind="other_income", amount="50", occurred_on="2026-09-25").status_code == 409  # the cash drawer's signed count refuses it too
    assert entry(admin, kind="other_income", amount="50").status_code == 201  # today is a different month
    assert admin.get("/api/journal/trial-balance", params={"as_of": "2026-09-30"}).json()["balanced"]


def test_reopening_needs_the_admin_permission_and_a_reason_and_goes_latest_first(admin):
    acct, _ = users(admin)
    ready_to_close(admin)
    assert acct.post("/api/periods/2026-09/close", json={}).status_code == 200  # the accountant may close
    assert acct.post("/api/periods/2026-09/reopen", json={"reason": "Forgot a receipt"}).status_code == 403
    assert admin.post("/api/periods/2026-09/reopen", json={"reason": "x"}).status_code == 422
    r = admin.post("/api/periods/2026-09/reopen", json={"reason": "Forgot a receipt"}).json()
    assert r["status"] == "open" and r["reopen_reason"] == "Forgot a receipt" and r["reopened_by"] == "Administrator"
    assert entry(admin, kind="other_income", amount="50", occurred_on="2026-09-25").status_code == 409  # day 25 is covered by the signed cash close, not the month
    assert admin.post("/api/periods/2026-09/reopen", json={"reason": "Again please"}).status_code == 409  # it isn't closed any more


def test_earlier_months_with_entries_must_be_closed_first(admin):
    entry(admin, kind="other_income", amount="100", occurred_on="2026-08-10")
    september(admin)
    for r in admin.get("/api/missing-evidence").json()["rows"]:
        admin.post("/api/missing-evidence/sign", json={"source_type": r["source_type"], "source_id": r["id"], "reason": "Small cash items, no slips"})
    admin.post("/api/cash-closes", json={"account": "cash", "close_date": "2026-08-31", "counted": "100"})
    admin.post("/api/cash-closes", json={"account": "cash", "close_date": "2026-09-30", "counted": "800"})
    cl = admin.get("/api/periods/2026-09/checklist").json()
    assert not cl["can_close"] and any(i["key"] == "earlier" and not i["ok"] for i in cl["items"])
    assert admin.post("/api/periods/2026-08/close", json={}).status_code == 200
    assert admin.post("/api/periods/2026-09/close", json={}).status_code == 200
    assert admin.post("/api/periods/2026-08/reopen", json={"reason": "Fix a mistake"}).status_code == 409  # September is closed after it


def test_a_year_closes_after_every_active_month_and_locks_everything_in_it(admin):
    assert admin.post("/api/periods/2026/close", json={}).status_code == 422  # not over
    entry(admin, kind="other_income", amount="100", occurred_on="2025-12-10")
    for r in admin.get("/api/missing-evidence").json()["rows"]:
        admin.post("/api/missing-evidence/sign", json={"source_type": r["source_type"], "source_id": r["id"], "reason": "Small cash items, no slips"})
    assert admin.post("/api/periods/2025/close", json={}).status_code == 409  # December is still open
    admin.post("/api/cash-closes", json={"account": "cash", "close_date": "2025-12-31", "counted": "100"})
    assert admin.post("/api/periods/2025-12/close", json={}).status_code == 200
    assert admin.post("/api/periods/2025/close", json={}).json()["status"] == "closed"
    assert entry(admin, kind="other_income", amount="5", occurred_on="2025-12-20").status_code == 409
    assert admin.post("/api/periods/2025-12/reopen", json={"reason": "A reason to try"}).status_code == 409  # the year is closed
    assert admin.post("/api/periods/2025/reopen", json={"reason": "Reopening the year"}).status_code == 200


def test_the_closing_pack_gathers_the_month(admin):
    ready_to_close(admin)
    pack = admin.get("/api/periods/2026-09/pack").json()
    assert D(str(pack["pnl"]["revenue"]["other"])) == 1000 and D(str(pack["pnl"]["total_expenses"])) == 300 and D(str(pack["pnl"]["net_profit"])) == 700
    assert D(str(pack["cashflow"]["accounts"]["cash"]["closing"])) == 700 and pack["cash_closes"][0]["counted"] == 700
    assert {e["source"] for e in pack["entries"]} == {"other_income", "expense"} and all(e["signoff"] for e in pack["entries"])
    assert pack["status"]["status"] == "open" and admin.get("/api/periods").json()["months"][-1]["period"] == "2026-09"


# --- reports ---------------------------------------------------------------------------------------------

def a_busy_month(admin):
    visit, item, ro = ready_repair(admin)  # labour 3000 + 2 filters (6000), cost 2000, 17% tax, 4000 advance
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    inv = admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}).json()
    entry(admin, kind="expense", category_id=category(admin, "Rent")["id"], amount="500")
    return visit, inv


def test_profit_and_loss_adds_up_from_the_journal(admin):
    a_busy_month(admin)
    p = admin.get("/api/reports/pnl").json()
    assert (D(str(p["revenue"]["labour"])), D(str(p["revenue"]["parts"])), D(str(p["revenue"]["total"]))) == (3000, 6000, 9000)
    assert D(str(p["cost_of_parts_sold"])) == 2000 and D(str(p["gross_profit"])) == 7000
    assert p["expenses_by_category"] == {"Rent": 500} and D(str(p["net_profit"])) == 6500
    assert D(str(p["sales_tax_collected"])) == 1530  # collected for the government, not income
    assert round(p["gross_margin_pct"], 1) == round(7000 / 9000 * 100, 1)
    assert D(str(admin.get("/api/reports/pnl", params={"date_from": "2020-01-01", "date_to": "2020-12-31"}).json()["revenue"]["total"])) == 0
    assert admin.get("/api/reports/pnl", params={"date_from": "2026-10-10", "date_to": "2026-10-01"}).status_code == 422


def test_cash_flow_reconciles_with_the_accounts(admin):
    a_busy_month(admin)
    cf = admin.get("/api/reports/cashflow").json()
    accounts = {a["kind"]: a for a in admin.get("/api/accounts").json()}
    for kind, a in cf["accounts"].items():
        assert D(str(a["closing"])) == D(str(accounts[kind]["balance"])) == D(str(a["opening"])) + D(str(a["in"])) - D(str(a["out"]))
    assert D(str(cf["closing"])) == D(str(cf["opening"])) + D(str(cf["in"])) - D(str(cf["out"]))
    assert "advance" in cf["accounts"]["cash"]["in_by_source"] or "payment" in cf["accounts"]["cash"]["in_by_source"]


def test_receivables_payables_and_stock_value_equal_the_books(admin):
    a_busy_month(admin)  # 6530 left to collect after the advance
    sent_po(admin)
    rec = admin.get("/api/reports/receivables").json()
    assert D(str(rec["total"])) == D(str(rows(admin)["1100"])) == 6530 and rec["by_bucket"] == {"0-30": 6530}
    vendor, item, po = sent_po(admin)
    grn = receive(admin, po, "10").json()["receipts"][0]
    unbilled = admin.get("/api/reports/payables").json()
    assert unbilled["by_bucket"] == {"not billed": 2000} and D(str(unbilled["total"])) == -D(str(rows(admin)["2100"])) == 2000
    admin.post(f"/api/goods-receipts/{grn['id']}/bill", json={"bill_date": date.today().isoformat()})
    pay = admin.get("/api/reports/payables").json()
    b = rows(admin)
    assert D(str(pay["total"])) == -(b["2000"] + b.get("2100", 0)) == 2000 and pay["rows"][0]["bucket"] == "not yet due"
    stock = admin.get("/api/reports/stock-value").json()
    assert D(str(stock["total"])) == D(str(rows(admin)["1200"]))


def test_month_end_cash_count_must_be_on_the_last_day(admin):
    september(admin)
    for r in admin.get("/api/missing-evidence").json()["rows"]:
        admin.post("/api/missing-evidence/sign", json={"source_type": r["source_type"], "source_id": r["id"], "reason": "Small cash items, no slips"})
    assert admin.post("/api/cash-closes", json={"account": "cash", "close_date": "2026-10-01", "counted": "700"}).status_code == 201
    cl = admin.get("/api/periods/2026-09/checklist").json()
    assert any(i["key"] == "cash_cash" and not i["ok"] for i in cl["items"]) and not cl["can_close"]


def test_closing_pack_freezes_owed_figures_and_shows_equity(admin):
    """Payments after as_of must not clear receivables; the pack freezes AR/AP/stock at period end and shows equity."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app import reports
    from app.config import local_today
    from app.db import SessionLocal
    from app.models import Branch, Payment
    from test_phase3_billing import CASH

    visit, inv = a_busy_month(admin)
    assert admin.post(f"/api/invoices/{inv['id']}/payments", json={"amount": "6530", **CASH}).status_code == 201
    assert D(str(admin.get("/api/reports/receivables").json()["total"])) == 0
    with SessionLocal() as db:
        pay = db.scalar(select(Payment).where(Payment.invoice_id == inv["id"], Payment.kind == "invoice"))
        pay.received_at = datetime.now(timezone.utc) + timedelta(days=2)
        db.commit()
        branch = db.scalar(select(Branch))
        assert D(str(reports.receivables(db, branch, as_of=local_today())["total"])) == 6530
        assert D(str(reports.stock_value(db, branch, as_of=local_today())["total"])) == D(str(rows(admin)["1200"]))
    ready_to_close(admin)
    pack = admin.get("/api/periods/2026-09/pack").json()
    assert D(str(pack["pnl"]["net_profit"])) == 700
    assert D(str(pack["equity"]["retained_earnings"])) == 700  # cumulative through 30 Sep = this month only here
    assert D(str(pack["equity"]["net_equity"])) == D(str(pack["equity"]["owner_capital"])) - D(str(pack["equity"]["owner_drawings"])) + 700
    assert pack["receivables"]["as_of"] == "2026-09-30" and D(str(pack["receivables"]["total"])) == 0
    assert pack["stock"]["as_of"] == "2026-09-30"


def test_operations_report_counts_the_workshop(admin):
    visit, inv = a_busy_month(admin)
    o = admin.get("/api/reports/operations").json()
    assert o["visits"]["total"] == 1 and o["visits"]["by_status"] == {"open": 1}
    assert D(str(o["revenue_by_channel"]["workshop"])) == 9000 and D(str(o["revenue_per_visit"])) == 9000
    assert o["top_labour"][0]["code"] == "SRV-OIL" and D(str(o["top_labour"][0]["revenue"])) == 3000
    assert o["top_parts"][0]["qty"] == 2 and o["quotations"] == {"made": 1, "sent": 1, "won": 1, "conversion_pct": 100.0}
    assert o["open_repair_orders_by_age"] == {"0-2 days": 1} and "received" in o["avg_hours_in_stage"]
    admin.post(f"/api/visits/{visit['id']}/gate-pass", json={"credit_reason": "Regular customer"})
    again = admin.get("/api/reports/operations").json()
    assert again["visits"]["avg_turnaround_hours"] is not None and again["visits"]["by_status"] == {"closed": 1}


def test_hr_report_and_discounts_and_voids(admin):
    staff(admin)
    h = admin.get("/api/reports/hr", params={"month": "2026-09"}).json()
    assert h["attendance"][0]["working_days"] == 5 and h["attendance"][0]["leave"] == 1
    visit, item, ro = ready_repair(admin)
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    inv = admin.put(f"/api/invoices/{inv['id']}", json={"prices": {}, "include_tax": True, "discount": "500", "version": inv["version"]}).json()
    admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]})
    e = entry(admin, kind="other_income", amount="75").json()
    admin.post(f"/api/money-entries/{e['id']}/void", json={"reason": "Typed twice"})
    d = admin.get("/api/reports/discounts").json()
    assert D(str(d["discount_total"])) == 500 and d["discounts_by_user"] == {"Administrator": 500}
    assert d["voids"][0]["reason"] == "Typed twice"


def test_the_dashboard_shows_money_only_to_finance_users(admin):
    a_busy_month(admin)
    full = admin.get("/api/dashboard").json()
    assert full["workshop"]["cars_in"] == 1 and full["workshop"]["repair_orders"] == 1
    assert D(str(full["money"]["revenue_month"])) == 9000 and D(str(full["money"]["receivables"])) == 6530
    assert full["alerts"]["missing_proof"] >= 1 and D(str(full["money"]["cash_total"])) == D(str(rows(admin)["1010"] + rows(admin)["1020"] + rows(admin)["1030"]))
    _, inv = users(admin)
    plain = inv.get("/api/dashboard").json()
    assert "money" not in plain and "alerts" not in plain and plain["workshop"]["cars_in"] == 1
    assert inv.get("/api/reports/pnl").status_code == 403 and inv.get("/api/reports/operations").status_code == 403
