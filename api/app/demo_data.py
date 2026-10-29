"""Load sample data so every main screen has something to open and click.

Uses the same HTTP API the UI uses, so stock movements and journals stay consistent.

    cd api
    # Needs a branch and admin (from app.seed) already in the database.
    set ADMIN_PASSWORD=your-password
    uv run python -m app.demo_data

    # Optional:
    uv run python -m app.demo_data --username owner --password secret

Safe to run again: if the marker customer (phone 0399 0000001) already exists,
the script prints what is there and exits without duplicating.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

from fastapi.testclient import TestClient

import app.events  # noqa: F401 — audit/outbox flush hooks
from app.main import app

CASH = {"account": "cash", "no_proof_reason": "Demo cash at the counter"}
MARKER_PHONE = "0399 0000001"
MARKER_NAME = "Demo Ali Khan"


def ok(r, label: str):
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise SystemExit(f"{label} failed ({r.status_code}): {detail}")
    return r.json() if r.content else None


def login(client: TestClient, username: str, password: str) -> None:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        raise SystemExit(f"Login failed ({r.status_code}): {r.text}. Seed an admin with `uv run python -m app.seed` first.")


def already_loaded(client: TestClient) -> bool:
    """True when the last demo step (HR employee) is present — a finished run."""
    rows = client.get("/api/employees", params={"q": "Demo Bilal"}).json()
    if isinstance(rows, dict):
        rows = rows.get("employees") or rows.get("items") or []
    return any("Demo Bilal" in (e.get("full_name") or "") for e in rows)


def find_customer(client, phone: str):
    digits = "".join(ch for ch in phone if ch.isdigit())[-10:]
    for c in client.get("/api/customers", params={"q": digits}).json():
        if digits in (c.get("phone") or "").replace("+", "").replace("-", ""):
            return c
    return None


def create_customer(client, name, phone, **extra):
    existing = find_customer(client, phone)
    if existing:
        return existing
    return ok(client.post("/api/customers", json={"name": name, "phone": phone, **extra}), f"customer {name}")


def find_car(client, plate: str):
    for c in client.get("/api/cars", params={"q": plate}).json():
        if (c.get("plate") or "").replace("-", "").replace(" ", "").upper() == plate.replace("-", "").replace(" ", "").upper():
            return c
    return None


def create_car(client, owner_id, plate, make="BMW", model="520i", **extra):
    existing = find_car(client, plate)
    if existing:
        return existing
    return ok(client.post("/api/cars", json={"owner_id": owner_id, "make": make, "model": model, "plate": plate, **extra}), f"car {plate}")


def create_item(client, name, codes, opening_qty="20", opening_cost="1000", sale_price="2500", **extra):
    code = codes[0][1]
    found = client.get("/api/items", params={"q": code}).json()
    if found:
        return found[0]
    body = {
        "name": name,
        "sale_price": sale_price,
        "codes": [{"kind": k, "code": c} for k, c in codes],
        "opening_qty": opening_qty,
        "opening_cost": opening_cost,
        **extra,
    }
    return ok(client.post("/api/items", json=body), f"item {name}")


def create_labour(client, code, name, category="Service"):
    found = client.get("/api/labour-codes", params={"q": code}).json()
    for row in found:
        if row.get("code") == code:
            return row
    return ok(client.post("/api/labour-codes", json={"code": code, "name": name, "category": category}), f"labour {code}")


def car_has_visit(client, car_id: str) -> bool:
    visits = client.get("/api/visits", params={"status": "all", "q": ""}).json()
    # Prefer car history when available
    hist = client.get(f"/api/cars/{car_id}/history")
    if hist.status_code == 200:
        return any(e.get("kind") == "visit" for e in hist.json())
    return False


def open_visit_for(client, car_id: str):
    for v in client.get("/api/visits", params={"status": "open"}).json():
        if v.get("car", {}).get("id") == car_id or v.get("car_id") == car_id:
            return v
    return None


def money_setup(client) -> None:
    accounts = ok(client.get("/api/accounts"), "accounts")
    cash = next(a for a in accounts if a["kind"] == "cash")
    if float(cash["opening_balance"]) == 0:
        ok(client.put(f"/api/accounts/{cash['id']}", json={
            "name": cash["name"] or "Cash drawer",
            "opening_balance": "50000",
            "opening_date": date.today().isoformat(),
            "version": cash["version"],
        }), "cash opening")
    ok(client.get("/api/expense-categories"), "expense categories")


def completed_job(client, customer, car, labour, item) -> dict:
    """Full workshop chain: visit → job → quote → RO → invoice → paid → gate pass."""
    if car_has_visit(client, car["id"]):
        print("  (completed job already present, skipping)")
        return {"visit": None, "invoice": None, "customer": customer, "car": car}
    odo = max(int(car.get("odometer_km") or 0) + 200, 82000)
    visit = ok(client.post("/api/visits", json={
        "car_id": car["id"], "odometer_in": odo, "fuel_eighths": 4,
        "complaint": "Oil service and rattling under the car",
    }), "check-in completed job")
    jc = ok(client.post(f"/api/visits/{visit['id']}/job-card"), "job card")
    lines = [
        {"kind": "labour", "labour_code_id": labour["id"]},
        {"kind": "part", "item_id": item["id"], "qty": "2"},
    ]
    jc = ok(client.put(f"/api/job-cards/{jc['id']}", json={"lines": lines, "version": jc["version"]}), "save job card")
    q = ok(client.post(f"/api/job-cards/{jc['id']}/quotation"), "start quotation")
    priced = [{k: l[k] for k in ("kind", "labour_code_id", "item_id", "qty")} | {"unit_price": "3500"} for l in q["lines"]]
    q = ok(client.put(f"/api/quotations/{q['id']}", json={
        "lines": priced, "include_tax": True, "valid_until": q["valid_until"], "version": q["version"],
    }), "price quotation")
    q = ok(client.post(f"/api/quotations/{q['id']}/send", json={"version": q["version"]}), "send quotation")
    q = ok(client.post(f"/api/quotations/{q['id']}/approve", json={
        "method": "phone", "no_proof_reason": "Approved on a call (demo)", "version": q["version"],
    }), "approve quotation")
    ok(client.post(f"/api/quotations/{q['id']}/advances", json={"amount": "5000", **CASH}), "advance")
    ro = ok(client.post(f"/api/quotations/{q['id']}/repair-order"), "repair order")
    url = f"/api/repair-orders/{ro['id']}"
    ok(client.post(f"{url}/status", json={"to": "in_repair", "version": ro["version"]}), "RO in repair")
    for l in client.get(url).json()["lines"]:
        if l["kind"] == "part":
            ok(client.post(f"{url}/lines/{l['id']}/issue", json={"qty": l["qty"]}), "issue part")
        ok(client.patch(f"{url}/lines/{l['id']}", json={"state": "done"}), "mark line done")
    ro = ok(client.post(f"{url}/status", json={"to": "ready", "version": client.get(url).json()["version"]}), "RO ready")
    inv = ok(client.post(f"{url}/invoice"), "workshop invoice")
    inv = ok(client.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}), "issue invoice")
    balance = inv["totals"]["balance"]
    if float(balance) > 0:
        inv = ok(client.post(f"/api/invoices/{inv['id']}/payments", json={"amount": str(balance), **CASH}), "pay invoice")
    visit = ok(client.post(f"/api/visits/{visit['id']}/gate-pass", json={
        "odometer_out": odo + 40, "handed_to": "Owner",
    }), "gate pass")
    return {"visit": visit, "invoice": inv, "customer": customer, "car": car}


def in_progress_job(client, customer, car, labour, item) -> dict:
    if open_visit_for(client, car["id"]) or car_has_visit(client, car["id"]):
        print("  (in-progress job already present, skipping)")
        return {"visit": open_visit_for(client, car["id"]), "ro": None}
    odo = max(int(car.get("odometer_km") or 0) + 100, 45000)
    visit = ok(client.post("/api/visits", json={
        "car_id": car["id"], "odometer_in": odo, "fuel_eighths": 6,
        "complaint": "Brakes squealing on the front",
    }), "check-in in progress")
    jc = ok(client.post(f"/api/visits/{visit['id']}/job-card"), "job card 2")
    lines = [
        {"kind": "labour", "labour_code_id": labour["id"]},
        {"kind": "part", "item_id": item["id"], "qty": "1"},
    ]
    jc = ok(client.put(f"/api/job-cards/{jc['id']}", json={"lines": lines, "version": jc["version"]}), "save job 2")
    q = ok(client.post(f"/api/job-cards/{jc['id']}/quotation"), "quote 2")
    priced = [{k: l[k] for k in ("kind", "labour_code_id", "item_id", "qty")} | {"unit_price": "4500"} for l in q["lines"]]
    q = ok(client.put(f"/api/quotations/{q['id']}", json={
        "lines": priced, "include_tax": True, "valid_until": q["valid_until"], "version": q["version"],
    }), "price quote 2")
    q = ok(client.post(f"/api/quotations/{q['id']}/send", json={"version": q["version"]}), "send quote 2")
    q = ok(client.post(f"/api/quotations/{q['id']}/approve", json={
        "method": "whatsapp", "no_proof_reason": "Customer replied OK on WhatsApp (demo)", "version": q["version"],
    }), "approve quote 2")
    ro = ok(client.post(f"/api/quotations/{q['id']}/repair-order"), "RO in progress")
    url = f"/api/repair-orders/{ro['id']}"
    ok(client.post(f"{url}/status", json={"to": "in_repair", "version": ro["version"]}), "RO in_repair")
    part = next(l for l in client.get(url).json()["lines"] if l["kind"] == "part")
    ok(client.post(f"{url}/lines/{part['id']}/issue", json={"qty": "1"}), "partial issue")
    return {"visit": visit, "ro": client.get(url).json()}


def draft_and_rejected_quotes(client, cars, labours, items) -> None:
    # Draft quotation only
    car = cars[2]
    if not open_visit_for(client, car["id"]):
        odo = max(int(car.get("odometer_km") or 0) + 100, 61000)
        visit = ok(client.post("/api/visits", json={
            "car_id": car["id"], "odometer_in": odo, "complaint": "AC not cooling",
        }), "check-in draft quote")
        jc = ok(client.post(f"/api/visits/{visit['id']}/job-card"), "jc draft")
        jc = ok(client.put(f"/api/job-cards/{jc['id']}", json={
            "lines": [{"kind": "labour", "labour_code_id": labours[2]["id"]}],
            "version": jc["version"],
        }), "jc draft save")
        q = ok(client.post(f"/api/job-cards/{jc['id']}/quotation"), "draft quote")
        priced = [{k: l[k] for k in ("kind", "labour_code_id", "item_id", "qty")} | {"unit_price": "8000"} for l in q["lines"]]
        ok(client.put(f"/api/quotations/{q['id']}", json={
            "lines": priced, "include_tax": True, "valid_until": q["valid_until"], "version": q["version"],
        }), "save draft quote")
    else:
        print("  (draft quote visit already open, skipping)")

    # Sent then rejected (needs its own car — one open visit per car)
    car = cars[3]
    if open_visit_for(client, car["id"]) or any(
        q.get("status") == "rejected" for q in client.get("/api/quotations", params={"q": "DEM-04"}).json()
    ):
        print("  (rejected quote already present, skipping)")
        return
    odo = max(int(car.get("odometer_km") or 0) + 100, 96000)
    visit = ok(client.post("/api/visits", json={
        "car_id": car["id"], "odometer_in": odo, "complaint": "Wants a detail quote only",
    }), "check-in rejected")
    jc = ok(client.post(f"/api/visits/{visit['id']}/job-card"), "jc reject")
    jc = ok(client.put(f"/api/job-cards/{jc['id']}", json={
        "lines": [
            {"kind": "labour", "labour_code_id": labours[0]["id"]},
            {"kind": "part", "item_id": items[1]["id"], "qty": "1"},
        ],
        "version": jc["version"],
    }), "jc reject save")
    q = ok(client.post(f"/api/job-cards/{jc['id']}/quotation"), "reject quote")
    priced = [{k: l[k] for k in ("kind", "labour_code_id", "item_id", "qty")} | {"unit_price": "12000"} for l in q["lines"]]
    q = ok(client.put(f"/api/quotations/{q['id']}", json={
        "lines": priced, "include_tax": True, "valid_until": q["valid_until"], "version": q["version"],
    }), "price reject quote")
    q = ok(client.post(f"/api/quotations/{q['id']}/send", json={"version": q["version"]}), "send reject quote")
    ok(client.post(f"/api/quotations/{q['id']}/reject", json={
        "reason": "Too expensive for now (demo)", "version": q["version"],
    }), "reject quotation")


def cancelled_visit(client, car) -> None:
    if car_has_visit(client, car["id"]):
        print("  (cancelled visit already present, skipping)")
        return
    odo = max(int(car.get("odometer_km") or 0) + 50, 12000)
    visit = ok(client.post("/api/visits", json={
        "car_id": car["id"], "odometer_in": odo, "complaint": "Changed their mind at the gate",
    }), "check-in cancel")
    ok(client.post(f"/api/visits/{visit['id']}/cancel", json={"reason": "Customer left without waiting (demo)"}), "cancel visit")


def purchasing(client, items) -> dict:
    vendors = client.get("/api/vendors", params={"q": "Demo Auto Parts"}).json()
    if vendors:
        print("  (demo vendor already present, skipping purchasing)")
        return {"vendor": vendors[0], "bill": None}
    vendor = ok(client.post("/api/vendors", json={
        "name": "Demo Auto Parts Wholesale", "phone": "0399 0000099", "terms_days": 14,
    }), "vendor")
    po = ok(client.post("/api/purchase-orders", json={
        "vendor_id": vendor["id"],
        "lines": [
            {"item_id": items[0]["id"], "qty": "10", "unit_cost": "900"},
            {"item_id": items[2]["id"], "qty": "5", "unit_cost": "1500"},
        ],
    }), "create PO")
    po = ok(client.post(f"/api/purchase-orders/{po['id']}/send", json={"version": po["version"]}), "send PO")
    receipt = ok(client.post(f"/api/purchase-orders/{po['id']}/receive", json={
        "lines": [{"po_line_id": l["id"], "qty": l["qty"], "unit_cost": l["unit_cost"]} for l in po["lines"]],
    }), "receive PO")
    grn = receipt["receipts"][0]
    today = date.today().isoformat()
    bill = ok(client.post(f"/api/goods-receipts/{grn['id']}/bill", json={
        "bill_date": today, "vendor_invoice_no": f"DEMO-{date.today().strftime('%Y%m%d')}",
    }), "vendor bill")
    ok(client.post(f"/api/bills/{bill['id']}/payments", json={
        "amount": str(bill["total"]), **CASH,
    }), "pay vendor bill")
    # A second PO left as sent (not received) so the list shows an open order
    draft_item = items[3]
    po2 = ok(client.post("/api/purchase-orders", json={
        "vendor_id": vendor["id"],
        "lines": [{"item_id": draft_item["id"], "qty": "8", "unit_cost": "600"}],
    }), "PO open")
    ok(client.post(f"/api/purchase-orders/{po2['id']}/send", json={"version": po2["version"]}), "send PO open")
    return {"vendor": vendor, "bill": bill}


def counter_sale(client, item) -> dict:
    existing = client.get("/api/invoices", params={"q": "Walk-in"}).json()
    if existing:
        print("  (counter sales already present, skipping)")
        return {"draft": None, "issued": existing[0]}
    line = {"kind": "part", "item_id": item["id"], "qty": "1", "unit_price": item["sale_price"]}
    cs = ok(client.post("/api/counter-sales", json={
        "lines": [line], "include_tax": False,
        "walk_in_name": "Walk-in Bilal (demo)", "walk_in_phone": "0399 0000088",
    }), "counter sale draft")
    # Leave one as draft; create and finish another
    item2_lines = {"kind": "part", "item_id": item["id"], "qty": "1", "unit_price": item["sale_price"]}
    cs2 = ok(client.post("/api/counter-sales", json={
        "lines": [item2_lines], "include_tax": True,
        "walk_in_name": "Walk-in Sara (demo)", "walk_in_phone": "0399 0000087",
    }), "counter sale 2")
    total = cs2["totals"]["total"]
    ok(client.post(f"/api/invoices/{cs2['id']}/issue", json={
        "version": cs2["version"],
        "payments": [{"amount": str(total), **CASH}],
    }), "finish counter sale")
    return {"draft": cs, "issued": cs2}


def money_book(client) -> None:
    page = client.get("/api/money-in", params={"q": "DEMO-OWN-1"}).json()
    if any(r.get("reference") == "DEMO-OWN-1" for r in page.get("rows") or []):
        print("  (demo money entries already present, skipping)")
        return
    cats = ok(client.get("/api/expense-categories"), "categories")
    rent = next((c for c in cats if c["name"] == "Rent"), cats[0])
    ok(client.post("/api/money-entries", json={
        "kind": "owner_capital", "amount": "100000", "account": "bank",
        "reference": "DEMO-OWN-1", "no_proof_reason": "Demo owner deposit",
    }), "owner capital")
    ok(client.post("/api/money-entries", json={
        "kind": "expense", "amount": "15000", "account": "cash",
        "category_id": rent["id"], "party": "Landlord (demo)",
        "no_proof_reason": "Demo rent paid in cash",
    }), "expense")
    ok(client.post("/api/money-entries", json={
        "kind": "other_income", "amount": "2500", "account": "cash",
        "party": "Scrap dealer (demo)", "no_proof_reason": "Demo scrap sale",
    }), "other income")
    ok(client.post("/api/money-entries", json={
        "kind": "transfer", "amount": "10000", "account": "bank", "to_account": "cash",
        "reference": "DEMO-ATM-1", "no_proof_reason": "Demo ATM withdrawal",
    }), "transfer")


def hr_sample(client) -> None:
    employees = client.get("/api/employees", params={"q": "Demo Bilal"}).json()
    if isinstance(employees, dict):
        employees = employees.get("employees") or employees.get("items") or []
    if any("Demo Bilal" in (e.get("full_name") or "") for e in employees):
        print("  (demo employees already present, skipping)")
        return
    e1 = ok(client.post("/api/employees", json={
        "full_name": "Demo Bilal Ahmed", "joined_on": "2026-01-01",
        "monthly_salary": "75000", "device_pin": "101", "phone": "0399 0000071",
    }), "employee 1")
    e2 = ok(client.post("/api/employees", json={
        "full_name": "Demo Sara Malik", "joined_on": "2026-03-15",
        "monthly_salary": "65000", "device_pin": "102", "phone": "0399 0000072",
        "title": "Technician",
    }), "employee 2")
    devices = client.get("/api/attendance-devices").json()
    device = next((d for d in devices if d.get("serial") == "DEMO-ZK-1001"), None)
    if not device:
        device = ok(client.post("/api/attendance-devices", json={
            "serial": "DEMO-ZK-1001", "name": "Demo front door", "use_secret": False,
        }), "attendance device")
    # A few punches this month so attendance has rows
    today = date.today()
    day = today.replace(day=1)
    lines = []
    while day <= today and day.weekday() != 6:  # skip Sundays
        pin = "101"
        lines.append((pin, f"{day.isoformat()} 09:00:00", "0", "1"))
        lines.append((pin, f"{day.isoformat()} 18:00:00", "1", "1"))
        day += timedelta(days=1)
        if len(lines) >= 10:
            break
    if lines:
        body = "\n".join("\t".join(l) for l in lines)
        r = client.post("/iclock/cdata", params={"SN": device["serial"], "table": "ATTLOG"}, content=body)
        if r.status_code >= 400:
            print(f"  (attendance push skipped: {r.status_code} {r.text})")
    # Leave mark on employee 2
    ok(client.post("/api/attendance/marks", json={
        "employee_id": e2["id"], "day": date.today().isoformat(),
        "kind": "paid_leave", "reason": "Demo family day",
    }), "leave mark")
    print(f"  Employees: {e1['number']}, {e2['number']}")


def run(username: str, password: str) -> None:
    with TestClient(app) as client:
        login(client, username, password)
        if already_loaded(client):
            print("Demo data already present (found Demo Bilal Ahmed). Nothing to do.")
            print("Browse customers, visits, invoices, purchase orders, money in/out, and employees.")
            return

        print("Setting up money accounts…")
        money_setup(client)

        print("Catalogue (labour codes + stock)…")
        labours = [
            create_labour(client, "DEMO-OIL", "Oil service", "Service"),
            create_labour(client, "DEMO-BRK", "Brake job", "Brakes"),
            create_labour(client, "DEMO-AC", "AC gas and leak check", "AC"),
            create_labour(client, "DEMO-DIAG", "Computer diagnosis", "Diagnostics"),
        ]
        items = [
            create_item(client, "Demo oil filter", (("barcode", "8900000000001"), ("mpn", "DEMO-OF-1")),
                        opening_qty="30", opening_cost="800", sale_price="1800", category="Filters"),
            create_item(client, "Demo brake pad set", (("barcode", "8900000000002"),),
                        opening_qty="12", opening_cost="3500", sale_price="7500", category="Brakes"),
            create_item(client, "Demo cabin filter", (("barcode", "8900000000003"),),
                        opening_qty="15", opening_cost="600", sale_price="1400", category="Filters"),
            create_item(client, "Demo wiper blade", (("barcode", "8900000000004"),),
                        opening_qty="20", opening_cost="400", sale_price="950", category="Wipers"),
            create_item(client, "Demo engine oil 5W-30", (("barcode", "8900000000005"),),
                        opening_qty="40", opening_cost="1200", sale_price="2200", category="Fluids", unit="litre"),
        ]

        print("Customers and cars…")
        customers = [
            create_customer(client, MARKER_NAME, MARKER_PHONE, cnic="3520211111111"),
            create_customer(client, "Demo Fatima Noor", "0399 0000002"),
            create_customer(client, "Demo Hassan Raza", "0399 0000003"),
            create_customer(client, "Demo City Motors", "0399 0000004", kind="company"),
            create_customer(client, "Demo Ayesha Khan", "0399 0000005"),
            create_customer(client, "Demo Omar Sheikh", "0399 0000006"),
        ]
        cars = [
            create_car(client, customers[0]["id"], "DEM-01-1001", make="BMW", model="520i", year=2018, odometer_km=81000, vin="WBA3A5C55DF123456"),
            create_car(client, customers[1]["id"], "DEM-02-2002", make="Toyota", model="Corolla", year=2020, odometer_km=44000, vin="NZE141-6012345"),
            create_car(client, customers[2]["id"], "DEM-03-3003", make="Honda", model="Civic", year=2019, odometer_km=60000),
            create_car(client, customers[3]["id"], "DEM-04-4004", make="Audi", model="A4", year=2017, odometer_km=95000),
            create_car(client, customers[4]["id"], "DEM-05-5005", make="Suzuki", model="Swift", year=2022, odometer_km=11000),
            create_car(client, customers[5]["id"], "DEM-06-6006", make="Mercedes", model="C200", year=2016, odometer_km=120000),
        ]

        print("Completed workshop job…")
        done = completed_job(client, customers[0], cars[0], labours[0], items[0])
        if done.get("visit"):
            print(f"  Visit {done['visit']['number']} → invoice paid, gate pass closed")

        print("In-progress repair…")
        prog = in_progress_job(client, customers[1], cars[1], labours[1], items[1])
        if prog.get("visit") and prog.get("ro"):
            print(f"  Visit {prog['visit']['number']}, RO {prog['ro']['number']} in repair")

        print("Draft and rejected quotations…")
        draft_and_rejected_quotes(client, cars, labours, items)

        print("Cancelled visit…")
        cancelled_visit(client, cars[4])

        print("Purchasing (PO → GRN → bill → pay)…")
        purchasing(client, items)

        print("Counter sales…")
        counter_sale(client, items[3])

        print("Money in / out…")
        money_book(client)

        print("HR (employees + attendance)…")
        hr_sample(client)

        print()
        print("Demo data loaded. Sign in and try:")
        print("  • Cars in the workshop / Visits (open + closed)")
        print("  • Quotations (draft, approved, rejected)")
        print("  • Repair orders, invoices, counter sales")
        print("  • Purchase orders and bills")
        print("  • Money in / Money out")
        print("  • Employees and attendance")
        print(f"  Search marker customer: {MARKER_NAME} / {MARKER_PHONE}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Load demo data into the local GermanATO database")
    ap.add_argument("--username", default=os.environ.get("ADMIN_USERNAME", "owner"))
    ap.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD"))
    args = ap.parse_args()
    password = args.password
    if not password:
        try:
            import getpass
            password = getpass.getpass(f"Password for {args.username}: ")
        except Exception:
            raise SystemExit("Pass --password or set ADMIN_PASSWORD")
    run(args.username.lower(), password)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
