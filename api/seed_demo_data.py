"""
Seed demo workshop data through the running API so foundation features
(branch header, idempotency, validation, audit reason) are exercised.

Usage (API must be running on :8000):
  .venv\\Scripts\\python.exe seed_demo_data.py
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"
BRANCH = "a1b2c3d4"


def call(method: str, path: str, token: str | None = None, body: dict | None = None, *, reason: str | None = None, idempotent: bool = False):
    headers = {
        "Content-Type": "application/json",
        "X-Branch-Id": BRANCH,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if reason:
        headers["X-Audit-Reason"] = reason
    if idempotent:
        headers["Idempotency-Key"] = str(uuid.uuid4())

    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {"error": str(exc)}
        except json.JSONDecodeError:
            payload = {"error": raw or str(exc)}
        return exc.code, payload
    except URLError as exc:
        print(f"API not reachable at {BASE}: {exc}")
        sys.exit(1)


def main() -> int:
    print("Logging in…")
    status, login = call("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})
    if status >= 400:
        print("Login failed:", login)
        return 1
    token = login["access_token"]
    print("  ok")

    today = date.today()
    iso_today = today.isoformat()

    print("Creating customer…")
    status, customer = call(
        "POST",
        "/api/customers",
        token,
        {
            "name": "Ahmed Khan",
            "phone": "03001234567",
            "address": "Gulberg III, Lahore",
        },
        reason="Demo seed",
    )
    print(f"  {status}", customer if status >= 400 else customer.get("customer") or customer)
    customer_id = None
    if isinstance(customer, dict):
        customer_id = (
            customer.get("id")
            or (customer.get("customer") or {}).get("id")
            or (customer.get("data") or {}).get("id")
        )

    # Re-fetch customers if create response shape differs
    if not customer_id:
        _, customers = call("GET", "/api/customers", token)
        if isinstance(customers, list) and customers:
            customer_id = customers[0].get("id")
            print(f"  using existing customer {customer_id}")

    print("Creating car…")
    status, car = call(
        "POST",
        "/api/cars",
        token,
        {
            "make": "Toyota",
            "model": "Corolla 2018",
            "plate_no": "LEA-2026",
            "mileage": "85400",
            "vin": "JTDBR32E520123456",
            "color": "White",
            "customer_id": customer_id,
        },
        reason="Demo seed",
    )
    print(f"  {status}", car if status >= 400 else "ok")
    car_id = None
    if isinstance(car, dict):
        car_id = car.get("id") or (car.get("car") or {}).get("id")

    print("Creating inventory parts…")
    parts = [
        {
            "name": "Oil Filter",
            "category": "Filters",
            "quantity": 25,
            "price": 850,
            "barcode": "8901001001001",
            "reorder_level": 5,
        },
        {
            "name": "Brake Pad Set",
            "category": "Brakes",
            "quantity": 8,
            "price": 4500,
            "barcode": "8901001001002",
            "reorder_level": 4,
        },
        {
            "name": "Engine Oil 4L",
            "category": "Lubricants",
            "quantity": 3,
            "price": 6200,
            "barcode": "8901001001003",
            "reorder_level": 6,
        },
    ]
    for part in parts:
        status, res = call("POST", "/api/inventory", token, part, reason="Demo seed inventory")
        print(f"  {part['name']}: {status}", "" if status < 400 else res)

    print("Creating quote (idempotent)…")
    quote_body = {
        "customer_name": "Ahmed Khan",
        "customer_address": "Gulberg III, Lahore",
        "customer_phone": "03001234567",
        "customer_reg_no": "LEA-2026",
        "customer_made": "Toyota Corolla 2018",
        "customer_mileage": "85400",
        "customer_id": customer_id,
        "car_id": car_id,
        "type_of": "quote",
        "advance": 0,
        "discount": 0,
        "include_tax": False,
        "tax_amount": 0,
        "items": [
            {"product_name": "Oil Filter", "part_number": "", "quantity": 1, "price": 850},
            {"product_name": "Engine Oil 4L", "part_number": "", "quantity": 1, "price": 6200},
        ],
        "labours": [{"description": "Oil change labour", "price": 1500}],
    }
    status, quote = call("POST", "/api/add", token, quote_body, reason="Demo quote", idempotent=True)
    print(f"  {status}", quote if status >= 400 else f"quote id={quote.get('id') or (quote.get('invoice') or {}).get('id')}")

    print("Creating invoice (idempotent)…")
    invoice_body = {
        **quote_body,
        "type_of": "invoice",
        "advance": 2000,
        "items": [
            {"product_name": "Brake Pad Set", "part_number": "", "quantity": 1, "price": 4500},
            {"product_name": "Oil Filter", "part_number": "", "quantity": 1, "price": 850},
        ],
        "labours": [
            {"description": "Brake service", "price": 2500},
            {"description": "Inspection", "price": 500},
        ],
    }
    status, invoice = call(
        "POST", "/api/add", token, invoice_body, reason="Demo invoice", idempotent=True
    )
    inv_id = None
    if isinstance(invoice, dict):
        inv_id = invoice.get("id") or (invoice.get("invoice") or {}).get("id")
    print(f"  {status}", invoice if status >= 400 else f"invoice id={inv_id}")

    print("Creating repair order…")
    status, ro = call(
        "POST",
        "/api/repair-orders",
        token,
        {
            "customer_name": "Ahmed Khan",
            "customer_phone": "03001234567",
            "customer_address": "Gulberg III, Lahore",
            "customer_reg_no": "LEA-2026",
            "customer_made": "Toyota Corolla 2018",
            "customer_mileage": "85400",
            "customer_id": customer_id,
            "car_id": car_id,
            "problem_description": "Squeaky brakes and due for oil service",
            "diagnosis_plan": "Replace pads, oil + filter",
            "current_status": "received",
            "parts": [
                {"description": "Brake Pad Set", "quantity": 1, "status": "pending"},
                {"description": "Oil Filter", "quantity": 1, "status": "pending"},
            ],
            "labour": [
                {"description": "Brake service", "status": "pending"},
                {"description": "Oil change", "status": "pending"},
            ],
        },
        reason="Demo repair order",
    )
    print(f"  {status}", ro if status >= 400 else "ok")

    print("Creating vendor + PO…")
    status, vendor = call(
        "POST",
        "/api/vendors",
        token,
        {
            "name": "AutoParts Hub",
            "company_name": "AutoParts Hub Pvt Ltd",
            "contact_person": "Bilal",
            "phone": "03211234567",
            "email": "sales@autopartshub.pk",
            "address": "Hall Road, Lahore",
            "cnic": "3520212345671",
        },
        reason="Demo vendor",
    )
    vendor_id = None
    if isinstance(vendor, dict):
        vendor_id = vendor.get("id") or (vendor.get("vendor") or {}).get("id")
    print(f"  vendor {status}", vendor if status >= 400 else f"id={vendor_id}")

    if not vendor_id:
        _, vendors = call("GET", "/api/vendors", token)
        if isinstance(vendors, list) and vendors:
            vendor_id = vendors[0].get("id")

    if vendor_id:
        status, po = call(
            "POST",
            "/api/purchase-orders/add",
            token,
            {
                "vendor_id": vendor_id,
                "date": iso_today,
                "invoice_no": f"PO-{today.strftime('%Y%m%d')}-1",
                "item_name": "Brake Pad Set",
                "quantity": 10,
                "rate": 3200,
                "remarks": "Demo consignment",
                "status": "ordered",
            },
            reason="Demo PO",
            idempotent=True,
        )
        print(f"  PO {status}", po if status >= 400 else "ok")

    print("Creating expenses…")
    for i, (cat, desc, amount) in enumerate(
        [
            ("Utilities", "Workshop electricity bill", 18500),
            ("Supplies", "Cleaning supplies", 2200),
            ("Rent", "Shop rent October", 75000),
        ],
        start=1,
    ):
        status, exp = call(
            "POST",
            "/api/expenses",
            token,
            {
                "date": (today - timedelta(days=i)).isoformat(),
                "category": cat,
                "description": desc,
                "amount": amount,
                "notes": "Demo seed",
            },
            reason="Demo expense",
            idempotent=True,
        )
        print(f"  {desc}: {status}", "" if status < 400 else exp)

    print("Creating cash received…")
    status, cash = call(
        "POST",
        "/api/cash-received",
        token,
        {
            "date": iso_today,
            "description": "Advance from Ahmed Khan",
            "amount": 2000,
            "payment_method": "cash",
            "notes": "Demo payment",
            "invoice_id": inv_id,
        },
        reason="Demo cash in",
        idempotent=True,
    )
    print(f"  {status}", cash if status >= 400 else "ok")

    print("Creating worker…")
    status, worker = call(
        "POST",
        "/api/workers",
        token,
        {
            "employee_id": "EMP001",
            "first_name": "Usman",
            "last_name": "Ali",
            "phone": "03331234567",
            "address": "Township, Lahore",
            "cnic": "3520298765432",
            "date_of_birth": "1995-04-12",
            "hire_date": "2024-01-15",
            "position": "Technician",
            "department": "Workshop",
            "salary": 45000,
            "status": "active",
        },
        reason="Demo worker",
    )
    print(f"  {status}", worker if status >= 400 else "ok")

    print("\nFetching reports…")
    status, reports = call(
        "GET",
        f"/api/reports?start_date={(today.replace(day=1)).isoformat()}&end_date={iso_today}",
        token,
    )
    if status >= 400:
        print("  reports failed:", reports)
    else:
        print(
            "  sales total:",
            (reports.get("sales") or {}).get("total"),
            "| expenses:",
            (reports.get("expenses") or {}).get("total"),
            "| profit:",
            (reports.get("profit") or {}).get("total"),
            "| receivables:",
            reports.get("receivables"),
        )

    print("\nDemo seed complete. Refresh Reports in the browser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
