"""
Additive shared-data foundation migration.

Safe to re-run. Adds permanent codes/document numbers, actor columns,
gate_pass table, and backfills codes from existing integer ids.
Does not rewrite or drop data.
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.document_numbers import (
    car_code,
    cash_document_no,
    customer_code,
    expense_document_no,
    invoice_document_no,
    po_document_no,
    repair_order_document_no,
    vendor_code,
)

COLUMNS: dict[str, dict[str, str]] = {
    "customer": {
        "code": "VARCHAR(20)",
        "created_by_user": "VARCHAR(80)",
        "updated_by_user": "VARCHAR(80)",
    },
    "car": {
        "code": "VARCHAR(20)",
        "created_by_user": "VARCHAR(80)",
        "updated_by_user": "VARCHAR(80)",
    },
    "invoice": {
        "document_no": "VARCHAR(40)",
    },
    "repair_order": {
        "document_no": "VARCHAR(40)",
    },
    "expense": {
        "document_no": "VARCHAR(40)",
        "created_by_user": "VARCHAR(80)",
        "updated_by_user": "VARCHAR(80)",
    },
    "cash_received": {
        "document_no": "VARCHAR(40)",
        "created_by_user": "VARCHAR(80)",
        "updated_by_user": "VARCHAR(80)",
    },
    "purchase_orders": {
        "document_no": "VARCHAR(40)",
        "updated_by_user": "VARCHAR(80)",
    },
    "vendors": {
        "code": "VARCHAR(20)",
        "created_by_user": "VARCHAR(80)",
        "updated_by_user": "VARCHAR(80)",
    },
}


def _existing_columns(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add_columns() -> None:
    for table, cols in COLUMNS.items():
        existing = _existing_columns(table)
        if not existing:
            continue
        with engine.begin() as conn:
            for name, ddl in cols.items():
                if name in existing:
                    continue
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
                print(f"  + {table}.{name}")


def _unique_index(table: str, column: str, index_name: str) -> None:
    existing = _existing_columns(table)
    if column not in existing:
        return
    insp = inspect(engine)
    indexes = {ix["name"] for ix in insp.get_indexes(table)}
    if index_name in indexes:
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS {index_name} '
                    f'ON "{table}" ({column}) WHERE {column} IS NOT NULL'
                )
            )
        print(f"  + unique index {index_name}")
    except Exception as exc:
        # Fallback without partial index (SQLite / older PG)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(f'CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON "{table}" ({column})')
                )
            print(f"  + unique index {index_name} (non-partial)")
        except Exception as exc2:
            print(f"  (skip index {index_name}: {exc} / {exc2})")


def _backfill() -> None:
    db = SessionLocal()
    try:
        from app.models import (
            Car,
            CashReceived,
            Customer,
            Expense,
            Invoice,
            PurchaseOrder,
            RepairOrder,
            Vendor,
        )

        n = 0
        for c in db.query(Customer).filter(Customer.code.is_(None)).all():
            c.code = customer_code(c.id)
            n += 1
        for c in db.query(Car).filter(Car.code.is_(None)).all():
            c.code = car_code(c.id)
            n += 1
        for v in db.query(Vendor).filter(Vendor.code.is_(None)).all():
            v.code = vendor_code(v.id)
            n += 1
        for inv in db.query(Invoice).filter(Invoice.document_no.is_(None)).all():
            inv.document_no = invoice_document_no(inv.id, type_of=inv.type_of)
            n += 1
        for ro in db.query(RepairOrder).filter(RepairOrder.document_no.is_(None)).all():
            ro.document_no = repair_order_document_no(ro.id)
            n += 1
        for e in db.query(Expense).filter(Expense.document_no.is_(None)).all():
            e.document_no = expense_document_no(e.id)
            n += 1
        for cr in db.query(CashReceived).filter(CashReceived.document_no.is_(None)).all():
            cr.document_no = cash_document_no(cr.id)
            n += 1
        for po in db.query(PurchaseOrder).filter(PurchaseOrder.document_no.is_(None)).all():
            po.document_no = po_document_no(po.id)
            n += 1
        db.commit()
        print(f"  backfilled {n} codes/document numbers")
    except Exception as exc:
        db.rollback()
        print(f"  (backfill error: {exc})")
        raise
    finally:
        db.close()


def main() -> int:
    print("Creating tables (gate_pass, etc.) if needed...")
    Base.metadata.create_all(bind=engine)

    print("Adding shared foundation columns...")
    _add_columns()

    print("Ensuring unique indexes on codes...")
    _unique_index("customer", "code", "uq_customer_code")
    _unique_index("car", "code", "uq_car_code")
    _unique_index("vendors", "code", "uq_vendor_code")
    _unique_index("invoice", "document_no", "uq_invoice_document_no")
    _unique_index("repair_order", "document_no", "uq_ro_document_no")
    _unique_index("expense", "document_no", "uq_expense_document_no")
    _unique_index("cash_received", "document_no", "uq_cash_document_no")
    _unique_index("purchase_orders", "document_no", "uq_po_document_no")
    _unique_index("gate_pass", "document_no", "uq_gate_pass_document_no")

    print("Backfilling permanent codes from existing ids...")
    _backfill()

    print("Shared data foundation migration complete.")
    print(
        "Schema summary:\n"
        "  customer.code, car.code, vendors.code\n"
        "  invoice/repair_order/expense/cash_received/purchase_orders.document_no\n"
        "  created_by_user/updated_by_user on customer, car, expense, cash, vendors\n"
        "  gate_pass table (direction, customer_id, car_id, visit_id, repair_order_id)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
