"""
Additive store / UOM columns on inventory.

Safe to re-run. Adds unit, pack_size, valuation_method, preferred_vendor_id.
Existing rows keep working (defaults: pcs / pack_size=1 / avg).
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import engine
import app.models  # noqa: F401


STORE_COLUMNS = {
    "unit": "VARCHAR(20) DEFAULT 'pcs'",
    "pack_size": "INTEGER DEFAULT 1",
    "valuation_method": "VARCHAR(20) DEFAULT 'avg'",
    "preferred_vendor_id": "INTEGER NULL REFERENCES vendors(id)",
}

CHECK_CONSTRAINTS = [
    ("inventory", "ck_inventory_pack_size_pos", "pack_size IS NULL OR pack_size >= 1"),
    ("inventory", "ck_inventory_quantity_nonneg", "quantity >= 0"),
]


def _existing_columns(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add_columns(table: str, columns: dict[str, str]) -> None:
    existing = _existing_columns(table)
    if not existing:
        print(f"  skip {table} (missing)")
        return
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name in existing:
                continue
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
            print(f"  + {table}.{name}")


def _add_checks() -> None:
    insp = inspect(engine)
    dialect = engine.dialect.name
    if dialect == "sqlite":
        print("  skip CHECKs on sqlite (create_all / app layer enforce)")
        return
    with engine.begin() as conn:
        for table, name, expr in CHECK_CONSTRAINTS:
            if table not in insp.get_table_names():
                continue
            existing = {c["name"] for c in insp.get_check_constraints(table)}
            if name in existing:
                continue
            # Clean bad rows before quantity >= 0 if needed
            if "quantity" in expr:
                conn.execute(text(f'UPDATE "{table}" SET quantity = 0 WHERE quantity < 0'))
            try:
                conn.execute(
                    text(f'ALTER TABLE "{table}" ADD CONSTRAINT {name} CHECK ({expr})')
                )
                print(f"  + CHECK {table}.{name}")
            except Exception as exc:  # noqa: BLE001
                print(f"  ! CHECK {name}: {exc}")


def main() -> int:
    print("migrate_inventory_store …")
    _add_columns("inventory", STORE_COLUMNS)
    _add_checks()
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
