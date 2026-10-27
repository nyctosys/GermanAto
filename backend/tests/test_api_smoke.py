from datetime import date, timedelta

import pytest

from conftest import body, login

TODAY = date.today()
YMD = TODAY.isoformat()


def ok(r, status=200):
    assert r.status_code == status, (r.status_code, body(r))
    return body(r)


# --- auth & permissions ---------------------------------------------------

def test_login_rejects_bad_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_api_requires_token(client):
    assert client.get("/api/inventory").status_code == 401


def test_auth_endpoints(client, admin, contract):
    contract("auth_login", client.post("/api/auth/login", json={"username": "admin", "password": "pw"}))
    contract("auth_verify", client.get("/api/auth/verify", headers=admin))
    contract("auth_users", client.get("/api/auth/users", headers=admin))
    contract("auth_roles_permissions", client.get("/api/auth/roles-permissions", headers=admin))
    contract("auth_permissions_my", client.get("/api/auth/permissions/my", headers=admin))


def test_role_fallbacks(client):
    acct, inv = login(client, "acct"), login(client, "inv")
    assert client.post("/api/inventory", headers=acct, json={}).status_code == 403
    assert client.get("/api/admin/app-logs", headers=acct).status_code == 403
    assert client.get("/api/auth/users", headers=inv).status_code == 403
    assert client.get("/api/inventory", headers=inv).status_code == 200


# --- end-to-end business flow, then a GET sweep over the seeded data -------

@pytest.fixture
def seeded(client, admin):
    ids = {}
    ok(client.post("/api/settings/categories", headers=admin, json={"name": "Engine"}), 201)
    ok(client.post("/api/settings/departments", headers=admin, json={"name": "Workshop"}), 201)

    customer = ok(client.post("/api/customers", headers=admin,
                              json={"name": "Ali Khan", "phone": "03001234567", "address": "Lahore"}), 201)
    ids["customer"] = customer.get("customer", customer).get("id") or customer.get("customer_id")
    car = ok(client.post("/api/cars", headers=admin, json={
        "customer_id": ids["customer"], "plate_no": "LEA-123", "make": "Toyota",
        "model": "Corolla", "mileage": "50000"}), 201)
    ids["car"] = car.get("car", car).get("id") or car.get("car_id")

    item = ok(client.post("/api/inventory", headers=admin, json={
        "name": "Oil filter", "category": "Engine", "quantity": 10, "reorder_level": 2,
        "barcode": "8901234567890"}), 201)
    ids["item"] = item.get("item", item).get("id")
    ids["part_number"] = item.get("item", item).get("part_number")

    inv = ok(client.post("/api/add", headers=admin, json={
        "customer_name": "Ali Khan", "customer_address": "Lahore", "customer_phone": "03001234567",
        "customer_reg_no": "LEA-123", "customer_made": "Toyota", "customer_mileage": "50000",
        "customer_id": ids["customer"], "car_id": ids["car"], "type_of": "invoice", "advance": 500,
        "items": [{"product_name": "Oil filter", "part_number": ids["part_number"], "quantity": 2, "price": 1500}],
        "labours": [{"description": "Oil change", "price": 1000}]}), 201)
    ids["invoice"] = inv["invoice_id"]
    quote = ok(client.post("/api/add", headers=admin, json={
        "customer_name": "Ali Khan", "type_of": "quote",
        "items": [{"product_name": "Oil filter", "quantity": 1, "price": 1500}], "labours": []}), 201)
    ids["quote"] = quote["invoice_id"]

    ro = ok(client.post("/api/repair-orders", headers=admin, json={
        "customer_name": "Ali Khan", "customer_reg_no": "LEA-123", "problem_description": "Noise",
        "parts": [{"description": "Oil filter", "quantity": 1, "inventory_id": ids["item"],
                   "part_number": ids["part_number"]}],
        "labour": [{"description": "Inspection"}]}), 201)
    ids["repair_order"] = ro.get("repair_order", ro).get("id") or ro.get("repair_order_id")

    ok(client.post("/api/expenses", headers=admin, json={
        "date": YMD, "category": "Utilities", "description": "Electricity", "amount": 2000}), 201)
    ok(client.post("/api/cash-received", headers=admin, json={
        "date": YMD, "description": "Walk-in", "amount": 3000, "payment_method": "Cash"}), 201)

    vendor = ok(client.post("/api/vendors", headers=admin, json={
        "name": "Bilal", "company_name": "Parts Co", "contact_person": "Bilal",
        "phone": "03007654321", "address": "Karachi"}), 201)
    ids["vendor"] = vendor.get("vendor", vendor).get("id") or vendor.get("vendor_id")
    ok(client.post("/api/ledger/add", headers=admin, json={
        "vendor_id": ids["vendor"], "date": YMD, "description": "Stock", "debit": 5000, "credit": 0}), 201)
    ok(client.post("/api/purchase-orders/add", headers=admin, json={
        "vendor_id": ids["vendor"], "date": YMD, "invoice_no": "PO-1", "item_name": "Oil filter",
        "quantity": 5, "rate": 900}), 201)

    worker = ok(client.post("/api/workers", headers=admin, json={
        "employee_id": "E001", "first_name": "Usman", "last_name": "Ali", "phone": "03111234567",
        "address": "Lahore", "cnic": "35202-1234567-1", "date_of_birth": "1990-01-01",
        "hire_date": "2024-01-01", "position": "Mechanic", "department": "Workshop", "salary": 40000}), 201)
    ids["worker"] = worker.get("worker", worker).get("id") or worker.get("worker_id")
    ok(client.post("/api/attendance", headers=admin, json={
        "worker_id": ids["worker"], "date": YMD, "check_in_time": "09:00", "check_out_time": "18:00"}), 201)
    ok(client.post("/api/salary/advances", headers=admin, json={
        "worker_id": ids["worker"], "amount": 5000, "date": YMD}), 201)
    return ids


def test_stock_moves_with_documents(client, admin, seeded):
    item = ok(client.get(f"/api/inventory/{seeded['item']}", headers=admin))
    item = item.get("item", item)
    # 10 received; the repair order part deducts 1. Invoices don't deduct (disabled in routes.py).
    assert item["quantity"] == 9


def test_invoice_balance(client, admin, seeded):
    inv = ok(client.get(f"/api/invoice/{seeded['invoice']}", headers=admin))
    inv = inv.get("invoice", inv)
    assert inv["net_total"] == 4000  # 2 x 1500 + 1000 labour
    assert inv["balance"] == 3500    # minus 500 advance


def test_get_sweep(client, admin, seeded, contract):
    s, y, m = seeded, TODAY.year, TODAY.month
    paths = {
        "health": "/api/health",
        "dashboard": "/api/dashboard",
        "reports": "/api/reports",
        "admin_app_logs": "/api/admin/app-logs",
        "search": "/api/search?query=Ali",
        "invoice": f"/api/invoice/{s['invoice']}",
        "invoice_log": f"/api/invoice/{s['invoice']}/log",
        "customers": "/api/customers",
        "customers_search": "/api/customers/search?q=Ali",
        "cars": "/api/cars",
        "car": f"/api/cars/{s['car']}",
        "cars_search": "/api/cars/search?q=LEA",
        "cars_for_customer": f"/api/cars/customer/{s['customer']}",
        "inventory": "/api/inventory",
        "inventory_item": f"/api/inventory/{s['item']}",
        "inventory_by_category": "/api/inventory/by-category?category=Engine",
        "inventory_search": "/api/inventory/search?q=Oil",
        "inventory_search_grouped": "/api/inventory/search-grouped?q=Oil",
        "inventory_categories": "/api/inventory/categories",
        "inventory_stats": "/api/inventory/stats",
        "inventory_low_stock": "/api/inventory/low-stock",
        "inventory_lookup": f"/api/inventory/lookup?code={s['part_number']}",
        "inventory_transactions": "/api/inventory/transactions",
        "inventory_item_transactions": f"/api/inventory/{s['item']}/transactions",
        "inventory_item_ledger": f"/api/inventory/{s['item']}/ledger",
        "repair_orders": "/api/repair-orders",
        "repair_order": f"/api/repair-orders/{s['repair_order']}",
        "repair_order_log": f"/api/repair-orders/{s['repair_order']}/log",
        "repair_order_logs": f"/api/repair-orders/{s['repair_order']}/logs",
        "repair_orders_assignable_workers": "/api/repair-orders/assignable-workers",
        "expenses": "/api/expenses",
        "expenses_summary": "/api/expenses/summary",
        "expenses_monthly_ledger": f"/api/expenses/monthly-ledger?month={y}-{m:02d}",
        "cash_received": "/api/cash-received",
        "cash_received_summary": "/api/cash-received/summary",
        "vendors": "/api/vendors",
        "vendor": f"/api/vendors/{s['vendor']}",
        "vendor_ledger": f"/api/vendors/{s['vendor']}/ledger",
        "vendor_purchase_orders": f"/api/vendors/{s['vendor']}/purchase-orders",
        "workers": "/api/workers",
        "worker": f"/api/workers/{s['worker']}",
        "workers_departments": "/api/workers/departments",
        "workers_positions": "/api/workers/positions",
        "attendance": "/api/attendance",
        "attendance_summary": f"/api/attendance/summary?worker_id={s['worker']}&year={y}&month={m}",
        "salary_calculate": f"/api/salary/calculate?worker_id={s['worker']}&month={m}&year={y}",
        "salary_advances": "/api/salary/advances",
        "payroll_preview": f"/api/salary/payroll/preview?year={y}&month={m}",
        "payroll": "/api/salary/payroll",
        "zkteco_devices": "/api/zkteco/devices",
        "settings_departments": "/api/settings/departments",
        "settings_categories": "/api/settings/categories",
        "financial_periods": "/api/financial-periods",
        "whatsapp_notifications": "/api/whatsapp/notifications",
        "whatsapp_stats": "/api/whatsapp/stats",
    }
    failures = []
    for name, path in paths.items():
        r = client.get(path, headers=admin)
        if r.status_code != 200:
            failures.append((path, r.status_code, body(r)))
            continue
        contract(name, r)
    assert not failures, failures


def test_document_lifecycle(client, admin, seeded):
    s = seeded
    ok(client.post(f"/api/invoice/{s['quote']}/convert", headers=admin))
    ok(client.put(f"/api/repair-orders/{s['repair_order']}/status", headers=admin, json={"status": "completed"}))
    ok(client.delete(f"/api/invoice/{s['invoice']}/delete", headers=admin))
    assert client.get(f"/api/invoice/{s['invoice']}", headers=admin).status_code == 404


def test_period_lock(client, admin):
    # Past months are closed by default; only admins may still write to them.
    last_month = (TODAY.replace(day=1) - timedelta(days=1)).isoformat()
    expense = {"date": last_month, "category": "Utilities", "description": "Late", "amount": 10}
    assert client.post("/api/expenses", headers=login(client, "acct"), json=expense).status_code == 403
    ok(client.post("/api/expenses", headers=admin, json=expense), 201)
    ok(client.post("/api/financial-periods", headers=admin, json={
        "year": int(last_month[:4]), "month": int(last_month[5:7]), "is_open": True, "reason": "fix"}))
    ok(client.post("/api/expenses", headers=login(client, "acct"), json=expense), 201)


def test_payroll_run(client, admin, seeded):
    ok(client.post("/api/salary/payroll/run", headers=admin,
                   json={"year": TODAY.year, "month": TODAY.month, "pay_date": YMD}), 201)
    runs = ok(client.get("/api/salary/payroll", headers=admin))
    assert runs


def test_zkteco_push_protocol(client):
    r = client.get("/iclock/getrequest?SN=TEST123")
    assert r.status_code == 200 and r.get_data(as_text=True).strip() == "OK"
    r = client.post("/iclock/cdata?SN=TEST123&table=OPERLOG", data="noop")
    assert r.status_code == 200 and r.get_data(as_text=True).strip() == "OK"
