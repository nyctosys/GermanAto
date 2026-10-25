"""Audit the reports module against hand-computed expected values.

Seeds a small, fully-known dataset, then compares every figure the reports
endpoint returns against the value computed independently from the seed.

Run against a THROWAWAY database - it calls drop_all():

    DATABASE_URL="mysql+pymysql://root@127.0.0.1:3306/germanato_test" \
        python test_reports_values.py
"""
import os
import sys

if not os.getenv("DATABASE_URL"):
    sys.exit("Refusing to run: set DATABASE_URL to a throwaway database (this drops all tables).")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime, timedelta
from app import app, db
from models import Invoice, RepairOrder, Expense, Customer, Car, Vendor, VendorLedger, Inventory
import reports_routes as rr

TODAY = date.today()
FAILURES = []


def check(label, actual, expected, note=""):
    ok = abs(actual - expected) < 0.01 if isinstance(expected, float) else actual == expected
    print(f"{'PASS' if ok else 'FAIL'}  {label:44s} got={actual!r:<12} expected={expected!r}"
          + (f"   <- {note}" if note and not ok else ""))
    if not ok:
        FAILURES.append((label, actual, expected, note))


def seed():
    db.drop_all()
    db.create_all()

    # --- Invoices (type_of='invoice') -----------------------------------
    # net_total, advance, paid_amount, discount, tax, balance
    invoices = [
        # fully unpaid: owes 10000
        dict(net_total=10000, advance=0,    paid_amount=0,    discount=0,   tax_amount=0,    balance=10000),
        # part-paid via paid_amount: owes 5000
        dict(net_total=8000,  advance=0,    paid_amount=3000, discount=0,   tax_amount=0,    balance=5000),
        # part-paid via ADVANCE only: owes 4000. Receivables must not ignore advance.
        dict(net_total=6000,  advance=2000, paid_amount=0,    discount=0,   tax_amount=0,    balance=4000),
        # fully paid: owes 0
        dict(net_total=5000,  advance=0,    paid_amount=5000, discount=0,   tax_amount=0,    balance=0),
        # with tax and discount: due = 4000 + 400 - 500 = 3900, paid 900 -> owes 3000
        dict(net_total=4000,  advance=400,  paid_amount=500,  discount=500, tax_amount=400,  balance=3000),
    ]
    for i, inv in enumerate(invoices):
        db.session.add(Invoice(
            customer_name=f"Cust {i}", customer_address="A", customer_phone="03001234567",
            customer_reg_no=f"REG{i}", customer_made="BMW", customer_mileage="1000",
            type_of="invoice", include_tax=bool(inv["tax_amount"]), created_at=datetime.combine(TODAY, datetime.min.time()) + timedelta(hours=1),
            **inv))

    # --- Quotes (type_of='quote', status pending) ------------------------
    for i in range(3):
        db.session.add(Invoice(
            customer_name=f"Quote Cust {i}", customer_address="A", customer_phone="03001234567",
            customer_reg_no=f"QREG{i}", customer_made="Audi", customer_mileage="1000",
            net_total=2000, advance=0, paid_amount=0, discount=0, tax_amount=0, balance=2000,
            type_of="quote", status="pending",
            created_at=datetime.combine(TODAY, datetime.min.time()) + timedelta(hours=2)))

    # --- Repair orders: the app's real vocabulary uses 'complete' --------
    ro_statuses = ["received", "diagnosis", "repair", "testing", "complete", "complete"]
    for i, st in enumerate(ro_statuses):
        db.session.add(RepairOrder(
            customer_name=f"RO Cust {i}", customer_phone="03001234567", customer_address="A",
            customer_reg_no=f"RREG{i}", customer_made="VW", customer_mileage="1000",
            current_status=st,
            created_at=datetime.combine(TODAY, datetime.min.time()),
            updated_at=datetime.combine(TODAY, datetime.min.time()) + timedelta(hours=3)))

    # --- Expenses: 1500 today --------------------------------------------
    for amt in (1000, 500):
        db.session.add(Expense(date=TODAY, category="fuel", description="d", amount=amt))

    db.session.commit()


EXPECTED = {
    # Sales = SUM(net_total) of invoices only (excludes the 3 quotes)
    "sales_total": 10000 + 8000 + 6000 + 5000 + 4000,          # 33000
    "expenses_total": 1500.0,
    # True amount owed = due - (advance + paid) per invoice, only where > 0
    "receivables_true": (10000 - 0) + (8000 - 3000) + (6000 - 2000) + 0 + (3900 - 900),  # 22000
    "open_repairs": 4,          # received, diagnosis, repair, testing
    "completed_today": 2,       # the two 'complete' rows updated today
    "pending_quotes": 3,
}

with app.app_context():
    seed()
    print(f"\nSeeded. Today = {TODAY}\n" + "=" * 92)

    start = datetime.combine(TODAY, datetime.min.time())
    end = datetime.combine(TODAY, datetime.max.time())

    sales = rr.get_sales_data(start, end)
    expenses = rr.get_expenses_data(start, end)
    profit = rr.calculate_profit(sales, expenses)

    print("\n--- Sales / expenses / profit ---")
    check("sales.total", sales["total"], float(EXPECTED["sales_total"]))
    check("expenses.total", expenses["total"], EXPECTED["expenses_total"])
    check("profit.total", profit["total"],
          float(EXPECTED["sales_total"]) - EXPECTED["expenses_total"])

    print("\n--- Receivables ---")
    check("receivables", rr.get_receivables(), float(EXPECTED["receivables_true"]),
          "ignores `advance`, tax and discount")

    print("\n--- Repair orders ---")
    check("open_repairs count", len(rr.get_open_repair_orders()), EXPECTED["open_repairs"],
          "filters != 'completed' but app writes 'complete'")
    check("completed_today count", len(rr.get_completed_repair_orders_today()), EXPECTED["completed_today"],
          "filters = 'completed' but app writes 'complete'")

    print("\n--- Quotes ---")
    check("pending_quotes count", len(rr.get_pending_quotes()), EXPECTED["pending_quotes"])

    print("\n" + "=" * 92)
    print(f"{len(FAILURES)} incorrect value(s)" if FAILURES else "All report values correct")
    for label, actual, expected, note in FAILURES:
        print(f"  - {label}: got {actual}, expected {expected} ({note})")

sys.exit(1 if FAILURES else 0)
