from decimal import Decimal

from test_phase2 import new_item
from test_phase3_visits import PNG, checked_in, upload


def setup_job(admin):
    visit, car, owner = checked_in(admin)
    code = admin.post("/api/labour-codes", json={"code": "SRV-OIL", "name": "Oil service", "category": "Service"}).json()
    item = new_item(admin)  # sale price 1500, no stock
    r = admin.post(f"/api/visits/{visit['id']}/job-card")
    assert r.status_code == 201
    jc = r.json()
    assert admin.post(f"/api/visits/{visit['id']}/job-card").status_code == 200  # opening again returns the same card
    lines = [{"kind": "labour", "labour_code_id": code["id"]}, {"kind": "part", "item_id": item["id"], "qty": "2"}]
    jc = admin.put(f"/api/job-cards/{jc['id']}", json={"lines": lines, "notes": "", "version": jc["version"]}).json()
    return visit, jc, code, item


def test_job_card_lists_codes_and_items_and_flags_shortage(admin):
    _, jc, _, _ = setup_job(admin)
    assert jc["number"].startswith("JC-") and [l["kind"] for l in jc["lines"]] == ["labour", "part"]
    assert Decimal(jc["lines"][1]["item"]["short"]) == 2
    bad = admin.put(f"/api/job-cards/{jc['id']}", json={"lines": [{"kind": "labour", "item_id": jc["lines"][1]["item_id"]}],
                                                       "version": jc["version"]})
    assert bad.status_code == 422  # free text or the wrong target is refused


def test_quotation_prices_send_approve_and_totals(admin):
    visit, jc, *_ = setup_job(admin)
    q = admin.post(f"/api/job-cards/{jc['id']}/quotation").json()
    assert q["status"] == "draft" and [Decimal(l["unit_price"]) for l in q["lines"]] == [0, 1500]
    assert admin.post(f"/api/job-cards/{jc['id']}/quotation").status_code == 409  # one current quotation per visit
    unpriced = admin.post(f"/api/quotations/{q['id']}/send", json={"version": q["version"]})
    assert unpriced.status_code == 422 and "Oil service" in unpriced.json()["detail"]

    lines = [{k: l[k] for k in ("kind", "labour_code_id", "item_id", "qty")} | {"unit_price": p}
             for l, p in zip(q["lines"], ["4000", "1500"])]
    q = admin.put(f"/api/quotations/{q['id']}", json={"lines": lines, "include_tax": True, "discount": "1000",
                                                     "valid_until": q["valid_until"], "version": q["version"]}).json()
    t = q["totals"]  # 4000 + 2 x 1500 = 7000, less 1000, plus 17% = 7020
    assert (Decimal(t["subtotal"]), Decimal(t["tax"]), Decimal(t["total"])) == (7000, 1020, 7020)

    q = admin.post(f"/api/quotations/{q['id']}/send", json={"version": q["version"]}).json()
    assert q["status"] == "sent"
    approve = {"method": "phone", "version": q["version"]}
    assert admin.post(f"/api/quotations/{q['id']}/approve", json=approve).status_code == 422  # no proof, no reason
    part = q["lines"][1]["id"]
    q = admin.post(f"/api/quotations/{q['id']}/approve",
                   json={**approve, "no_proof_reason": "Customer approved on a call", "declined_line_ids": [part]}).json()
    assert q["status"] == "approved" and q["approval"]["by"] == "Administrator"
    assert Decimal(q["totals"]["total"]) == Decimal("3510.00")  # the declined part drops out: (4000 - 1000) x 1.17

    rev = admin.post(f"/api/quotations/{q['id']}/revise").json()
    assert rev["revision"] == 2 and rev["number"] == q["number"] and rev["status"] == "draft"
    assert [r["status"] for r in rev["revisions"]] == ["revised", "draft"]
    assert not any(l["declined"] for l in rev["lines"])  # v2 needs its own approval
    assert admin.get(f"/api/visits/{visit['id']}").json()["quotations"][-1]["revision"] == 2


def test_advance_needs_a_sent_quote_and_blocks_cancelling(admin):
    visit, jc, *_ = setup_job(admin)
    q = admin.post(f"/api/job-cards/{jc['id']}/quotation").json()
    pay = {"amount": "5000", "account": "cash", "no_proof_reason": "Cash at the counter, no slip"}
    assert admin.post(f"/api/quotations/{q['id']}/advances", json=pay).status_code == 409  # still a draft

    lines = [{k: l[k] for k in ("kind", "labour_code_id", "item_id", "qty")} | {"unit_price": "2000"} for l in q["lines"]]
    q = admin.put(f"/api/quotations/{q['id']}", json={"lines": lines, "include_tax": False,
                                                     "valid_until": q["valid_until"], "version": q["version"]}).json()
    admin.post(f"/api/quotations/{q['id']}/send", json={"version": q["version"]})
    no_ref = admin.post(f"/api/quotations/{q['id']}/advances", json={**pay, "account": "bank"})
    assert no_ref.status_code == 422 and "reference" in no_ref.json()["detail"]  # a transfer needs its reference or a screenshot
    p = admin.post(f"/api/quotations/{q['id']}/advances", json=pay).json()
    assert p["number"].startswith("PAY-") and p["kind"] == "advance"
    shot = admin.post(f"/api/quotations/{q['id']}/advances",
                      json={"amount": "1000", "account": "wallet", "proof_id": upload(admin, PNG + b"jazzcash")})
    assert shot.status_code == 201 and shot.json()["proof_url"]

    q = admin.get(f"/api/quotations/{q['id']}").json()
    assert (Decimal(q["totals"]["advance"]), Decimal(q["totals"]["balance"])) == (6000, 0)  # labour 2000 + 2 parts x 2000, no tax
    assert admin.post(f"/api/visits/{visit['id']}/cancel", json={"reason": "Customer left"}).status_code == 409


def test_picker_finds_codes_names_and_scanned_barcodes(admin):
    setup_job(admin)
    assert [r["kind"] for r in admin.get("/api/estimate-catalog", params={"q": "oil"}).json()] == ["labour", "part"]
    scanned = admin.get("/api/estimate-catalog", params={"q": "4006 633 123 456"}).json()
    assert [r["name"] for r in scanned] == ["Oil filter"]


def test_inspection_repairs_go_to_the_job_card_once_with_their_estimate(admin):
    from test_phase3_visits import PNG, checked_in, upload
    visit, _, _ = checked_in(admin)
    code = admin.post("/api/labour-codes", json={"code": "IGN-COIL", "name": "Replace ignition coils", "category": "Engine"}).json()
    ins = admin.post(f"/api/visits/{visit['id']}/inspections", json={"kind": "workshop"}).json()
    data = ins["data"]
    data["repairs"] = [{"priority": "high", "repair": "Replace ignition coils", "estimated_cost": "45000"},
                       {"priority": "low", "repair": "Wash the engine bay", "estimated_cost": None}]
    data["assessment"].update(overall="average", recommendation="after_repairs")
    version = admin.put(f"/api/inspections/{ins['id']}", json={"data": data, "version": ins["version"]}).json()["version"]
    url = f"/api/inspections/{ins['id']}/repairs/0/send"
    pick = {"kind": "labour", "labour_code_id": code["id"]}
    assert admin.post(url, json=pick).status_code == 409  # still a draft: its rows could move
    admin.post(f"/api/inspections/{ins['id']}/sign", json={"inspector_signature_id": upload(admin, PNG + b"i"), "version": version})
    assert admin.post(f"/api/inspections/{ins['id']}/repairs/9/send", json=pick).status_code == 404

    jc = admin.post(url, json=pick)
    assert jc.status_code == 201, jc.json()
    line = jc.json()["lines"][0]
    assert line["note"] == "Replace ignition coils" and Decimal(str(line["proposed_price"])) == 45000
    assert admin.post(url, json=pick).status_code == 409  # each repair goes once
    assert list(admin.get(f"/api/inspections/{ins['id']}").json()["repairs_sent"]) == ["0"]
    assert admin.get(f"/api/visits/{visit['id']}").json()["job_card"]["lines"] == 1

    q = admin.post(f"/api/job-cards/{jc.json()['id']}/quotation").json()
    assert Decimal(str(q["lines"][0]["unit_price"])) == 45000  # the inspector's estimate starts the price
    send = admin.post(f"/api/quotations/{q['id']}/send", json={"version": q["version"]})
    assert send.status_code == 200  # no labour line left unpriced
    assert admin.post(f"/api/inspections/{ins['id']}/repairs/1/send", json=pick).status_code == 409  # the quotation exists now
