"""
Additive procurement / AP migration.

Safe to re-run. Adds vendor payment terms, PO expected delivery / approval,
and first-class goods_receipts / supplier_invoices / supplier_payments /
supplier_credit_notes tables. Existing ledger + PO data keeps working.
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import Base, engine
import app.models  # noqa: F401


VENDOR_COLUMNS = {
    "payment_terms_days": "INTEGER DEFAULT 30",
    "bank_details": "TEXT NULL",
    "notes": "TEXT NULL",
}

PO_COLUMNS = {
    "expected_delivery": "DATE NULL",
    "unit": "VARCHAR(20) NULL",
    "approved_at": "TIMESTAMP NULL",
    "approved_by_user": "VARCHAR(80) NULL",
}

LEDGER_COLUMNS = {
    "supplier_invoice_id": "INTEGER NULL",
    "supplier_payment_id": "INTEGER NULL",
    "supplier_credit_note_id": "INTEGER NULL",
    "goods_receipt_id": "INTEGER NULL",
}


def _existing_columns(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add_columns(table: str, columns: dict[str, str]) -> None:
    existing = _existing_columns(table)
    if not existing:
        return
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name in existing:
                continue
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
            print(f"  + {table}.{name}")


def _index_if_missing(table: str, name: str, cols: str) -> None:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    existing = {i["name"] for i in insp.get_indexes(table)}
    if name in existing:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE INDEX {name} ON "{table}" ({cols})'))
        print(f"  + INDEX {name}")
    except Exception as exc:
        print(f"  (skip index {name}: {exc})")


def main() -> int:
    print("Creating procurement tables if needed...")
    Base.metadata.create_all(bind=engine)

    print("Adding vendor AP columns...")
    _add_columns("vendors", VENDOR_COLUMNS)

    print("Adding purchase order approval / delivery columns...")
    _add_columns("purchase_orders", PO_COLUMNS)

    print("Adding vendor_ledger soft-link columns...")
    _add_columns("vendor_ledger", LEDGER_COLUMNS)

    _index_if_missing("vendor_ledger", "ix_vendor_ledger_supplier_invoice_id", "supplier_invoice_id")
    _index_if_missing("goods_receipts", "ix_goods_receipts_po_id", "purchase_order_id")
    _index_if_missing("supplier_invoices", "ix_supplier_invoices_due_date", "due_date")
    _index_if_missing("supplier_invoices", "ix_supplier_invoices_status", "status")

    print("Procurement migration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
