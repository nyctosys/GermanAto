from datetime import date, timedelta
from decimal import Decimal

from test_foundation import signed_in
from test_phase2 import new_item

CASH = {"account": "cash", "no_proof_reason": "Cash from the till"}
D = Decimal


def new_vendor(admin, name="Auto Parts Wholesale", **extra):
    r = admin.post("/api/vendors", json={"name": name, "phone": "0300 1112233", **extra})
    assert r.status_code == 201, r.json()
    return r.json()


_n = iter(range(1, 1000))


def sent_po(admin, qty="10", cost="200", **item_extra):
    """A new vendor and a new item (10 in stock at 100 each), and a sent order for more at 200."""
    n = next(_n)
    vendor = new_vendor(admin, name=f"Vendor {n}", terms_days=14)
    item = new_item(admin, name=f"Filter {n}", codes=(("barcode", f"40066331{n:05d}"),), opening_qty="10", opening_cost="100", **item_extra)
    po = admin.post("/api/purchase-orders", json={"vendor_id": vendor["id"], "lines": [{"item_id": item["id"], "qty": qty, "unit_cost": cost}]}).json()
    po = admin.post(f"/api/purchase-orders/{po['id']}/send", json={"version": po["version"]}).json()
    return vendor, item, po


def receive(admin, po, qty, cost="200", **extra):
    line = po["lines"][0]
    return admin.post(f"/api/purchase-orders/{po['id']}/receive", json={"lines": [{"po_line_id": line["id"], "qty": qty, "unit_cost": cost, **extra}]})


def item_state(admin, item):
    d = admin.get(f"/api/items/{item['id']}").json()
    return D(str(d["on_hand"])), D(str(d["avg_cost"])), D(str(d["sale_price"]))


def test_vendors_are_unique_by_name_and_normalised(admin):
    v = new_vendor(admin)
    assert v["number"] == "VEN-A1F3-000001" and v["phone"] == "+923001112233" and D(str(v["owed"])) == 0
    assert admin.post("/api/vendors", json={"name": "auto parts WHOLESALE", "phone": "0300 1"}).status_code in (409, 422)
    assert admin.post("/api/vendors", json={"name": "AUTO PARTS wholesale"}).status_code == 409
    assert admin.put(f"/api/vendors/{v['id']}", json={"name": "Auto Parts Wholesale", "terms_days": 30, "version": v["version"]}).status_code == 200


def test_purchase_order_lifecycle_and_weighted_average_cost(admin):
    vendor, item, po = sent_po(admin)
    assert po["number"].startswith("PO-") and po["status"] == "sent" and D(str(po["total"])) == 2000
    assert admin.put(f"/api/purchase-orders/{po['id']}", json={"vendor_id": vendor["id"], "lines": []}).status_code == 422
    draft = admin.put(f"/api/purchase-orders/{po['id']}", json={"vendor_id": vendor["id"], "lines": [
        {"item_id": item["id"], "qty": "10", "unit_cost": "200"}]})
    assert draft.status_code == 409  # sent orders are locked

    first = receive(admin, po, "4")
    assert first.status_code == 201, first.json()
    got = first.json()
    assert got["status"] == "partly_received" and D(str(got["lines"][0]["outstanding"])) == 6
    assert item_state(admin, item)[:2] == (14, D("128.5714"))  # (10 x 100 + 4 x 200) / 14

    assert receive(admin, po, "7").status_code == 422  # only 6 still expected
    last = receive(admin, po, "6").json()
    assert last["status"] == "received" and len(last["receipts"]) == 2
    on_hand, avg, _ = item_state(admin, item)
    assert on_hand == 20 and avg == D("150.0000")
    assert receive(admin, po, "1").status_code == 409  # fully received
    movements = admin.get(f"/api/items/{item['id']}").json()["movements"]
    assert [m["kind"] for m in movements].count("grn") == 2


def test_receiving_before_sending_and_empty_receipts_are_refused(admin):
    vendor = new_vendor(admin)
    item = new_item(admin)
    po = admin.post("/api/purchase-orders", json={"vendor_id": vendor["id"], "lines": [{"item_id": item["id"], "qty": "5", "unit_cost": "50"}]}).json()
    assert receive(admin, po, "5", "50").status_code == 409  # a draft
    po = admin.post(f"/api/purchase-orders/{po['id']}/send", json={"version": po["version"]}).json()
    assert receive(admin, po, "0", "50").status_code == 422
    dup = admin.post("/api/purchase-orders", json={"vendor_id": vendor["id"], "lines": [
        {"item_id": item["id"], "qty": "1", "unit_cost": "5"}, {"item_id": item["id"], "qty": "1", "unit_cost": "5"}]})
    assert dup.status_code == 422


def test_receipt_can_change_the_sale_price_and_warns_about_thin_margins(admin):
    _, item, po = sent_po(admin)  # 10 in stock at 100, sale price 1500
    got = receive(admin, po, "10", "5000", sale_price="2000").json()  # average becomes (1000 + 50000) / 20 = 2550
    assert item_state(admin, item) == (20, D("2550.0000"), D("2000.00"))
    assert any("above the sale price" in w for w in got["warnings"])

    _, item2, po2 = sent_po(admin)
    ok = receive(admin, po2, "10", "100", sale_price="1500").json()
    assert ok["warnings"] == []
    thin = receive(admin, sent_po(admin)[2], "10", "2700", sale_price="1500").json()  # average (1000 + 27000) / 20 = 1400
    assert any("margin is only" in w for w in thin["warnings"])


def test_cancel_and_close_rules(admin):
    vendor, item, po = sent_po(admin)
    assert admin.post(f"/api/purchase-orders/{po['id']}/close", json={"reason": "Vendor out of stock"}).status_code == 409  # nothing received
    receive(admin, po, "3")
    assert admin.post(f"/api/purchase-orders/{po['id']}/cancel", json={"reason": "Changed mind"}).status_code == 409
    closed = admin.post(f"/api/purchase-orders/{po['id']}/close", json={"reason": "Vendor out of stock"}).json()
    assert closed["status"] == "closed" and closed["closed_reason"] == "Vendor out of stock"
    assert receive(admin, po, "1").status_code == 409

    _, _, other = sent_po(admin)
    assert admin.post(f"/api/purchase-orders/{other['id']}/cancel", json={"reason": "x"}).status_code == 422  # a reason is needed
    assert admin.post(f"/api/purchase-orders/{other['id']}/cancel", json={"reason": "Ordered elsewhere"}).json()["status"] == "cancelled"


def test_bill_payments_and_the_derived_ledger(admin):
    vendor, item, po = sent_po(admin)
    grn = receive(admin, po, "10").json()["receipts"][0]  # 10 x 200 = 2000
    bill_url = f"/api/goods-receipts/{grn['id']}/bill"
    today = date.today().isoformat()
    assert admin.post(bill_url, json={"bill_date": today, "adjustment": "150"}).status_code == 422  # freight needs a reason
    assert admin.post(bill_url, json={"bill_date": (date.today() + timedelta(days=1)).isoformat()}).status_code == 422

    bill = admin.post(bill_url, json={"bill_date": today, "vendor_invoice_no": "INV-77", "adjustment": "150",
                                      "adjustment_reason": "Freight"}).json()
    assert bill["number"].startswith("BILL-") and D(str(bill["total"])) == 2150
    assert bill["due_on"] == (date.today() + timedelta(days=14)).isoformat()  # the vendor's terms
    assert admin.post(bill_url, json={"bill_date": today}).status_code == 409  # one bill per receipt

    # The same vendor invoice number can't be entered twice, even on another receipt.
    po2 = admin.post("/api/purchase-orders", json={"vendor_id": vendor["id"], "lines": [{"item_id": item["id"], "qty": "1", "unit_cost": "10"}]}).json()
    po2 = admin.post(f"/api/purchase-orders/{po2['id']}/send", json={"version": po2["version"]}).json()
    grn2 = receive(admin, po2, "1", "10").json()["receipts"][0]
    assert admin.post(f"/api/goods-receipts/{grn2['id']}/bill", json={"bill_date": today, "vendor_invoice_no": "inv-77"}).status_code == 409

    pay = f"/api/bills/{bill['id']}/payments"
    assert admin.post(pay, json={"amount": "1000", "account": "cash"}).status_code == 422  # proof or a reason
    assert admin.post(pay, json={"amount": "1000", "account": "bank", "no_proof_reason": "Slip to follow"}).status_code == 422  # reference
    assert admin.post(pay, json={"amount": "3000", **CASH}).status_code == 422  # more than owed
    part = admin.post(pay, json={"amount": "1000", **CASH}).json()
    assert part["pay_state"] == "partly_paid" and D(str(part["balance"])) == 1150
    assert part["payments"][0]["number"].startswith("VPAY-")
    assert admin.post(f"/api/bills/{bill['id']}/void", json={"reason": "Wrong vendor"}).status_code == 409  # money was paid

    wrong = admin.post(pay, json={"amount": "150", **CASH}).json()["payments"][-1]
    back = admin.post(f"/api/vendor-payments/{wrong['id']}/void", json={"reason": "Entered twice"}).json()
    assert D(str(back["balance"])) == 1150  # the voided payment owes again

    v = admin.get(f"/api/vendors/{vendor['id']}").json()
    assert D(str(v["owed"])) == 1150 and [e["kind"] for e in v["ledger"]][0] == "payment"
    assert D(str(v["ledger"][0]["balance"])) == 1150  # newest first; the running balance skips the voided payment
    assert D(str(admin.get("/api/vendors").json()[0]["owed"])) == 1150

    r = admin.post(pay, json={"amount": "1150", "account": "wallet", "reference": "JC-1", "no_proof_reason": "Screenshot to follow"})
    assert r.status_code == 201, r.json()
    paid = r.json()
    assert paid["pay_state"] == "paid" and D(str(admin.get(f"/api/vendors/{vendor['id']}").json()["owed"])) == 0
    assert [b["number"] for b in admin.get("/api/bills", params={"status": "owing"}).json()] == []


def test_voiding_an_unpaid_bill_lets_the_receipt_be_billed_again(admin):
    _, _, po = sent_po(admin)
    grn = receive(admin, po, "10").json()["receipts"][0]
    url = f"/api/goods-receipts/{grn['id']}/bill"
    bill = admin.post(url, json={"bill_date": date.today().isoformat(), "vendor_invoice_no": "A-1"}).json()
    assert admin.post(f"/api/bills/{bill['id']}/void", json={"reason": "Typed the wrong invoice"}).json()["status"] == "void"
    assert admin.post(url, json={"bill_date": date.today().isoformat(), "vendor_invoice_no": "A-2"}).status_code == 201
    assert len(admin.get("/api/bills", params={"status": "all"}).json()) == 1  # voided bills drop off the list


def test_permissions_split_the_work(admin):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    for name, role in (("buyer", "Inventory manager"), ("acct", "Accountant")):
        admin.post("/api/users", json={"username": name, "full_name": name.title(), "password": f"{name}-pass-123",
                                       "role_id": roles[role], "branch_ids": [branch_id]})
    buyer, acct = signed_in("buyer", "buyer-pass-123"), signed_in("acct", "acct-pass-123")
    vendor = new_vendor(buyer)  # the inventory manager buys
    item = new_item(buyer)
    po = buyer.post("/api/purchase-orders", json={"vendor_id": vendor["id"], "lines": [{"item_id": item["id"], "qty": "2", "unit_cost": "50"}]}).json()
    po = buyer.post(f"/api/purchase-orders/{po['id']}/send", json={"version": po["version"]}).json()
    grn = receive(buyer, po, "2", "50").json()["receipts"][0]
    bill = buyer.post(f"/api/goods-receipts/{grn['id']}/bill", json={"bill_date": date.today().isoformat()}).json()
    assert buyer.post(f"/api/bills/{bill['id']}/payments", json={"amount": "50", **CASH}).status_code == 403  # can't pay
    assert acct.post("/api/purchase-orders", json={"vendor_id": vendor["id"], "lines": []}).status_code == 403
    assert acct.post(f"/api/purchase-orders/{po['id']}/receive", json={"lines": []}).status_code == 403
    assert acct.post(f"/api/bills/{bill['id']}/payments", json={"amount": "50", **CASH}).status_code == 201  # the accountant pays
    assert acct.get("/api/bills").status_code == 200


def test_an_item_can_have_several_vendors_and_reorder_lists_follow_the_vendor(admin):
    a, b = new_vendor(admin, "Tyre House"), new_vendor(admin, "Battery Hub")
    tyre = new_item(admin, "Tyre", codes=(("barcode", "7000000000011"),), reorder_level="5")
    plain = new_item(admin, "Wiper", codes=(("barcode", "7000000000028"),), reorder_level="5")
    mine = admin.put(f"/api/items/{tyre['id']}/vendors", json=[{"vendor_id": a["id"], "unit_cost": "9000"}, {"vendor_id": b["id"]}]).json()
    assert {v["name"] for v in mine} == {"Tyre House", "Battery Hub"}
    assert admin.put(f"/api/items/{tyre['id']}/vendors", json=[{"vendor_id": a["id"]}, {"vendor_id": a["id"]}]).status_code == 422
    low = lambda vid: {i["name"]: i for i in admin.get("/api/items", params={"stock": "low", "vendor_id": vid}).json()}
    assert set(low(a["id"])) == {"Tyre", "Wiper"} and float(low(a["id"])["Tyre"]["vendor_cost"]) == 9000
    admin.put(f"/api/items/{tyre['id']}/vendors", json=[{"vendor_id": b["id"]}])
    assert set(low(a["id"])) == {"Wiper"}  # the tyre is now only bought from Battery Hub; the wiper has no vendor set
