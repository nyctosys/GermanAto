"""
Additive inventory / PO / stock migration.

Safe to re-run. Adds reserved/avg_cost/min-max/supersession columns,
PO receive fields, RO part ownership flags, and stock-movement columns
on inventory_transactions. Existing data keeps working.
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import Base, engine
import app.models  # noqa: F401


INVENTORY_COLUMNS = {
    "reserved": "INTEGER DEFAULT 0",
    "avg_cost": "NUMERIC(12,2) DEFAULT 0",
    "min_level": "INTEGER NULL",
    "max_level": "INTEGER NULL",
    "superseded_by_id": "INTEGER NULL REFERENCES inventory(id)",
    "alternate_codes": "TEXT NULL",
    "pending_purchase": "BOOLEAN DEFAULT FALSE",
}

PO_COLUMNS = {
    "inventory_id": "INTEGER NULL REFERENCES inventory(id)",
    "qty_received": "INTEGER DEFAULT 0",
    "receipt_attachment_path": "VARCHAR(255) NULL",
}

RO_PART_COLUMNS = {
    "ownership_type": "VARCHAR(30) DEFAULT 'shop_stock'",
    "old_parts_returned": "BOOLEAN DEFAULT FALSE",
}

TXN_COLUMNS = {
    "reserved_before": "INTEGER NULL",
    "reserved_after": "INTEGER NULL",
    "unit_cost": "NUMERIC(12,2) NULL",
    "purchase_order_id": "INTEGER NULL REFERENCES purchase_orders(id)",
    "reason": "VARCHAR(255) NULL",
    "evidence_path": "VARCHAR(255) NULL",
}

CHECK_CONSTRAINTS = [
    ("inventory", "ck_inventory_reserved_nonneg", "reserved >= 0"),
    ("inventory", "ck_inventory_avg_cost_nonneg", "avg_cost >= 0"),
    ("purchase_orders", "ck_po_qty_received_nonneg", "qty_received >= 0"),
]


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


def _widen_txn_type() -> None:
    if "transaction_type" not in _existing_columns("inventory_transactions"):
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE inventory_transactions "
                    "ALTER COLUMN transaction_type TYPE VARCHAR(30)"
                )
            )
        print("  ~ inventory_transactions.transaction_type -> VARCHAR(30)")
    except Exception as exc:
        print(f"  (skip txn type widen: {exc})")


def _add_checks() -> None:
    insp = inspect(engine)
    for table, name, expr in CHECK_CONSTRAINTS:
        if table not in insp.get_table_names():
            continue
        existing = {c["name"] for c in insp.get_check_constraints(table)}
        if name in existing:
            continue
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(f'ALTER TABLE "{table}" ADD CONSTRAINT {name} CHECK ({expr})')
                )
            print(f"  + CHECK {table}.{name}")
        except Exception as exc:
            print(f"  (skip CHECK {name}: {exc})")


def main() -> int:
    print("Creating tables if needed...")
    Base.metadata.create_all(bind=engine)

    print("Adding inventory stock columns...")
    _add_columns("inventory", INVENTORY_COLUMNS)

    print("Adding purchase order GRN columns...")
    _add_columns("purchase_orders", PO_COLUMNS)

    print("Adding repair order part ownership columns...")
    _add_columns("repair_order_part", RO_PART_COLUMNS)

    print("Extending inventory_transactions (stock movements)...")
    _widen_txn_type()
    _add_columns("inventory_transactions", TXN_COLUMNS)

    print("Backfilling reserved / qty_received / ownership defaults...")
    with engine.begin() as conn:
        if "reserved" in _existing_columns("inventory"):
            conn.execute(text("UPDATE inventory SET reserved = 0 WHERE reserved IS NULL"))
        if "avg_cost" in _existing_columns("inventory"):
            conn.execute(text("UPDATE inventory SET avg_cost = 0 WHERE avg_cost IS NULL"))
        if "pending_purchase" in _existing_columns("inventory"):
            conn.execute(
                text(
                    "UPDATE inventory SET pending_purchase = FALSE WHERE pending_purchase IS NULL"
                )
            )
        if "qty_received" in _existing_columns("purchase_orders"):
            conn.execute(
                text(
                    "UPDATE purchase_orders SET qty_received = 0 WHERE qty_received IS NULL"
                )
            )
        if "ownership_type" in _existing_columns("repair_order_part"):
            conn.execute(
                text(
                    "UPDATE repair_order_part SET ownership_type = 'shop_stock' "
                    "WHERE ownership_type IS NULL"
                )
            )
        if "old_parts_returned" in _existing_columns("repair_order_part"):
            conn.execute(
                text(
                    "UPDATE repair_order_part SET old_parts_returned = FALSE "
                    "WHERE old_parts_returned IS NULL"
                )
            )

    print("Adding CHECK constraints...")
    _add_checks()

    print("Inventory migration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
