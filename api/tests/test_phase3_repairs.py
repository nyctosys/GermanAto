from decimal import Decimal

from test_phase2 import new_item
from test_phase3_visits import PNG, checked_in, upload


def approved_quote(admin):
    """A visit with an approved quote: one labour line and 2 oil filters (6 in stock at 1000 each)."""
    visit, _, _ = checked_in(admin)
    code = admin.post("/api/labour-codes", json={"code": "SRV-OIL", "name": "Oil service", "category": "Service"}).json()
    item = new_item(admin, opening_qty="6", opening_cost="1000")
    jc = admin.post(f"/api/visits/{visit['id']}/job-card").json()
    lines = [{"kind": "labour", "labour_code_id": code["id"]}, {"kind": "part", "item_id": item["id"], "qty": "2"}]
    jc = admin.put(f"/api/job-cards/{jc['id']}", json={"lines": lines, "version": jc["version"]}).json()
    q = admin.post(f"/api/job-cards/{jc['id']}/quotation").json()
    priced = [{k: l[k] for k in ("kind", "labour_code_id", "item_id", "qty")} | {"unit_price": "3000"} for l in q["lines"]]
    q = admin.put(f"/api/quotations/{q['id']}", json={"lines": priced, "include_tax": True,
                                                     "valid_until": q["valid_until"], "version": q["version"]}).json()
    q = admin.post(f"/api/quotations/{q['id']}/send", json={"version": q["version"]}).json()
    return visit, item, code, q


def approve(admin, q, **extra):
    r = admin.post(f"/api/quotations/{q['id']}/approve", json={"method": "phone", "no_proof_reason": "Approved on a call",
                                                              "version": q["version"], **extra})
    assert r.status_code == 200, r.json()
    return r.json()


def stock(admin, item):
    return Decimal(admin.get(f"/api/items/{item['id']}").json()["on_hand"])


def test_repair_order_carries_approved_lines_only(admin):
    visit, _, _, q = approved_quote(admin)
    assert admin.post(f"/api/quotations/{q['id']}/repair-order").status_code == 409  # not approved yet
    q = approve(admin, q, declined_line_ids=[q["lines"][0]["id"]])
    ro = admin.post(f"/api/quotations/{q['id']}/repair-order").json()
    assert ro["number"].startswith("RO-") and ro["status"] == "received"
    assert [l["description"] for l in ro["lines"]] == ["Oil filter"]  # the declined labour stayed behind
    assert admin.get(f"/api/quotations/{q['id']}").json()["status"] == "converted"
    assert admin.post(f"/api/quotations/{q['id']}/repair-order").status_code == 409
    assert admin.get(f"/api/visits/{visit['id']}").json()["repair_order"]["id"] == ro["id"]


def test_parts_issue_and_return_through_stock(admin):
    visit, item, _, q = approved_quote(admin)
    ro = admin.post(f"/api/quotations/{approve(admin, q)['id']}/repair-order").json()
    base = f"/api/repair-orders/{ro['id']}"
    ro = admin.post(f"{base}/status", json={"to": "in_repair", "version": ro["version"]}).json()
    part = next(l for l in ro["lines"] if l["kind"] == "part")
    url = f"{base}/lines/{part['id']}"
    assert admin.patch(url, json={"state": "done"}).status_code == 422  # nothing issued yet
    assert admin.post(f"{url}/issue", json={"qty": "7"}).status_code == 422  # more than the line qty (2)
    assert admin.post(f"{url}/issue", json={"qty": "3"}).status_code == 422  # still over the line qty
    ro = admin.post(f"{url}/issue", json={"qty": "2"}).json()
    assert stock(admin, item) == 4
    ro = admin.post(f"{url}/return", json={"qty": "1"}).json()
    assert stock(admin, item) == 5 and Decimal(next(l for l in ro["lines"] if l["id"] == part["id"])["issued_qty"]) == 1
    assert admin.post(f"{url}/return", json={"qty": "5"}).status_code == 422
    assert Decimal(str(admin.get(f"/api/items/{item['id']}").json()["avg_cost"])) == 1000  # a return keeps the cost
    assert admin.post(f"/api/visits/{visit['id']}/cancel", json={"reason": "Changed mind"}).status_code == 409
    assert {a["kind"] for a in ro["activity"]} >= {"parts", "status"}


def test_status_rules_and_activity(admin):
    _, _, _, q = approved_quote(admin)
    ro = admin.post(f"/api/quotations/{approve(admin, q)['id']}/repair-order").json()
    url = f"/api/repair-orders/{ro['id']}"
    go = lambda to, **kw: admin.post(f"{url}/status", json={"to": to, "version": admin.get(url).json()["version"], **kw})
    assert go("in_repair").status_code == 200
    assert go("received").status_code == 422  # backwards needs a note
    assert go("received", note="Still booking the bay").status_code == 200
    assert go("in_repair").status_code == 200
    assert go("on_hold").status_code == 422
    held = go("on_hold", note="Waiting for parts").json()
    assert held["status"] == "on_hold" and held["held_from"] == "in_repair"
    assert go("in_repair").status_code == 200  # resuming needs no note
    assert "Mark these done" in go("testing").json()["detail"]
    assert "Testing first" in go("ready").json()["detail"]

    assert admin.get("/api/technicians").json() == []  # only employees offered for repair work appear
    admin.post("/api/employees", json={"full_name": "Bilal Ahmed", "title": "Technician", "joined_on": "2026-01-01"})
    admin.post("/api/employees", json={"full_name": "Front Desk", "joined_on": "2026-01-01", "is_technician": False})
    techs = admin.get("/api/technicians").json()
    assert [t["name"] for t in techs] == ["Bilal Ahmed"]
    tech = techs[0]
    for l in admin.get(url).json()["lines"]:
        if l["kind"] == "part":
            admin.post(f"{url}/lines/{l['id']}/issue", json={"qty": l["qty"]})
        r = admin.patch(f"{url}/lines/{l['id']}", json={"state": "done", "technician_id": tech["id"]})
        assert r.status_code == 200, r.json()
    assert go("testing").json()["status"] == "testing"
    assert go("ready").json()["status"] == "ready"

    r = admin.post(f"{url}/activity", json={"kind": "customer_update", "body": "Your car is ready, collect after 5pm",
                                           "photo_ids": [upload(admin, PNG + b"done")]})
    entry = r.json()["activity"][0]
    assert entry["customer_visible"] and entry["photos"] and entry["by"] == "Administrator"


def test_extra_work_is_flagged_and_removable(admin):
    _, item, code, q = approved_quote(admin)
    ro = admin.post(f"/api/quotations/{approve(admin, q)['id']}/repair-order").json()
    url = f"/api/repair-orders/{ro['id']}"
    base = {"kind": "labour", "labour_code_id": code["id"], "unit_price": "1500", "reason": "Found a leaking sump plug"}
    assert admin.post(f"{url}/lines", json={**base, "approval_method": "phone", "no_proof_reason": "Agreed on a call"}).status_code == 409  # still Received
    ro = admin.post(f"{url}/status", json={"to": "in_repair", "version": ro["version"]}).json()
    assert admin.post(f"{url}/lines", json={**base, "reason": "", "approval_method": "phone", "no_proof_reason": "Agreed on a call"}).status_code == 422  # reason
    assert admin.post(f"{url}/lines", json={**base}).status_code == 422  # how did the customer agree?
    assert admin.post(f"{url}/lines", json={**base, "approval_method": "phone"}).status_code == 422  # proof or a reason
    ro = admin.post(f"{url}/lines", json={**base, "approval_method": "phone", "no_proof_reason": "Agreed on a call"}).json()
    extra = ro["lines"][-1]
    assert extra["in_quote"] is False and extra["approval"] == {"method": "phone", "reason": "Agreed on a call", "proof_url": None}
    assert admin.delete(f"{url}/lines/{ro['lines'][0]['id']}").status_code == 409  # approved lines stay
    assert len(admin.delete(f"{url}/lines/{extra['id']}").json()["lines"]) == 2
