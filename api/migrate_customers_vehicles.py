"""
Additive customer / vehicle field migration.

Safe to re-run. Adds alternate phone, type, notes, consent flags on customer;
year, engine_no, notes on car. Does not rewrite or drop data.
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import engine
import app.models  # noqa: F401

COLUMNS: dict[str, dict[str, str]] = {
    "customer": {
        "alternate_phone": "VARCHAR(20)",
        "customer_type": "VARCHAR(40)",
        "notes": "TEXT",
        "consent_whatsapp": "BOOLEAN DEFAULT FALSE",
        "consent_sms": "BOOLEAN DEFAULT FALSE",
        "consent_call": "BOOLEAN DEFAULT TRUE",
    },
    "car": {
        "year": "INTEGER",
        "engine_no": "VARCHAR(50)",
        "notes": "TEXT",
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
            print(f"  skip {table} (missing)")
            continue
        with engine.begin() as conn:
            for name, ddl in cols.items():
                if name in existing:
                    continue
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
                print(f"  + {table}.{name}")


def _index(table: str, column: str, index_name: str) -> None:
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
                text(f'CREATE INDEX IF NOT EXISTS {index_name} ON "{table}" ({column})')
            )
            print(f"  + index {index_name}")
    except Exception as exc:
        print(f"  ! index {index_name}: {exc}")


def main() -> int:
    print("Migrating customer / vehicle fields…")
    _add_columns()
    _index("customer", "alternate_phone", "ix_customer_alternate_phone")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
