from decimal import Decimal

from test_foundation import signed_in
from test_phase2 import new_item
from test_phase3_repairs import approve, approved_quote, stock

CASH = {"account": "cash", "no_proof_reason": "Cash at the counter"}


def ready_repair(admin):
    """Approved quote (labour 3000 + 2 filters at 3000, 17% tax = 10530), 4000 advance, repair done and Ready."""
    visit, item, code, q = approved_quote(admin)
    q = approve(admin, q)
    admin.post(f"/api/quotations/{q['id']}/advances", json={"amount": "4000", **CASH})
    ro = admin.post(f"/api/quotations/{q['id']}/repair-order").json()
    url = f"/api/repair-orders/{ro['id']}"
    for l in ro["lines"]:
        if l["kind"] == "part":
            admin.post(f"{url}/lines/{l['id']}/issue", json={"qty": l["qty"]})
        admin.patch(f"{url}/lines/{l['id']}", json={"state": "done"})
    admin.post(f"{url}/status", json={"to": "ready", "version": admin.get(url).json()["version"]})
    return visit, item, admin.get(url).json()


def test_workshop_invoice_applies_advance_and_gate_pass_needs_payment(admin):
    visit, _, ro = ready_repair(admin)
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    assert inv["number"].startswith("INV-") and Decimal(inv["totals"]["advance_held"]) == 4000
    assert Decimal(inv["totals"]["total"]) == Decimal("10530.00")

    blocked = admin.get(f"/api/visits/{visit['id']}/gate-check").json()
    assert any("draft" in b for b in blocked["blockers"])
    inv = admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}).json()
    assert inv["status"] == "issued" and inv["pay_status"] == "partly_paid" and Decimal(inv["totals"]["balance"]) == 6530
    assert admin.put(f"/api/invoices/{inv['id']}", json={"include_tax": False, "version": inv["version"]}).status_code == 409

    assert admin.post(f"/api/invoices/{inv['id']}/payments", json={"amount": "7000", **CASH}).status_code == 422  # over balance
    gate = f"/api/visits/{visit['id']}/gate-pass"
    assert admin.post(gate, json={"odometer_out": 80020}).status_code == 422  # balance: admin must give a reason
    inv = admin.post(f"/api/invoices/{inv['id']}/payments", json={"amount": "6530", **CASH}).json()
    assert inv["pay_status"] == "paid"
    assert admin.post(f"/api/visits/{visit['id']}/cancel", json={"reason": "x" * 5}).status_code == 409

    done = admin.post(gate, json={"odometer_out": 80020, "handed_to": "Owner's driver"}).json()
    assert done["status"] == "closed" and done["repair_order"]["status"] == "delivered"
    assert admin.get(f"/api/cars/{done['car']['id']}").json()["odometer_km"] == 80020

    d = admin.get(f"/api/visits/{visit['id']}/dossier").json()
    assert d["gate_pass"]["handed_to"] == "Owner's driver" and d["invoices"][0]["number"] == inv["number"]
    assert d["job_card"] and d["quotations"] and d["repair_order"] and len(d["payments"]) == 2 and d["audit"]
    history = admin.get(f"/api/cars/{done['car']['id']}/history").json()
    assert any(e["kind"] == "invoice" for e in history)


def test_credit_release_needs_the_permission_and_a_reason(admin):
    visit, _, ro = ready_repair(admin)
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]})
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    role = admin.post("/api/roles", json={"name": "Front desk", "permissions": ["visits", "dashboard"]}).json()
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    admin.post("/api/users", json={"username": "desk", "full_name": "Desk", "password": "desk-pass-123",
                                   "role_id": role.get("id", roles.get("Front desk")), "branch_ids": [branch_id]})
    desk = signed_in("desk", "desk-pass-123")
    gate = f"/api/visits/{visit['id']}/gate-pass"
    assert desk.post(gate, json={"credit_reason": "Regular customer, pays monthly"}).status_code == 403
    v = admin.post(gate, json={"credit_reason": "Regular customer, pays monthly"}).json()
    assert v["status"] == "closed" and v["credit_reason"] == "Regular customer, pays monthly"
    assert admin.get(f"/api/invoices/{inv['id']}").json()["credit_release"]["by"] == "Administrator"


def test_invoice_must_match_the_repair_order(admin):
    _, _, ro = ready_repair(admin)
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    part = next(l for l in ro["lines"] if l["kind"] == "part")
    admin.post(f"/api/repair-orders/{ro['id']}/lines/{part['id']}/return", json={"qty": "1"})  # one filter came back
    first = inv["lines"][0]
    inv = admin.put(f"/api/invoices/{inv['id']}", json={"prices": {first["id"]: "3500"}, "include_tax": True,
                                                       "version": inv["version"]}).json()
    assert admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}).status_code == 409
    inv = admin.post(f"/api/invoices/{inv['id']}/refresh").json()
    assert [Decimal(l["qty"]) for l in inv["lines"] if l["kind"] == "part"] == [1]
    assert Decimal(inv["lines"][0]["unit_price"]) == 3500  # the edited price survived the refresh
    assert admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}).status_code == 200


def test_counter_sale_takes_stock_and_payment_together(admin):
    item = new_item(admin, name="Headlight", codes=(("mpn", "63117440"),), opening_qty="3", opening_cost="20000")
    line = {"kind": "part", "item_id": item["id"], "qty": "1", "unit_price": "30000"}
    assert admin.post("/api/counter-sales", json={"lines": [{**line, "kind": "labour", "item_id": None,
                                                            "labour_code_id": item["id"]}]}).status_code == 422
    cs = admin.post("/api/counter-sales", json={"lines": [line], "include_tax": False, "walk_in_name": "Walk-in Bilal",
                                               "walk_in_phone": "0300 1112223"}).json()
    assert cs["number"].startswith("CS-") and cs["walk_in_phone"] == "+923001112223"
    short = admin.post(f"/api/invoices/{cs['id']}/issue", json={"version": cs["version"], "payments": [{"amount": "20000", **CASH}]})
    assert short.status_code == 422 and stock(admin, item) == 3  # nothing moved
    split = [{"amount": "20000", **CASH}, {"amount": "10000", "account": "bank", "reference": "IBFT-1", "no_proof_reason": "Slip pending"}]
    r = admin.post(f"/api/invoices/{cs['id']}/issue", json={"version": cs["version"], "payments": split})
    assert r.status_code == 200, r.json()
    cs = r.json()
    assert cs["pay_status"] == "paid" and len(cs["payments"]) == 2 and stock(admin, item) == 2


def test_gate_pass_refuses_while_an_advance_is_held_without_an_invoice(admin):
    visit, _, _, q = approved_quote(admin)
    admin.post(f"/api/quotations/{q['id']}/advances", json={"amount": "1000", **CASH})
    r = admin.post(f"/api/visits/{visit['id']}/gate-pass", json={})
    assert r.status_code == 409 and "Refund" in r.json()["detail"]
