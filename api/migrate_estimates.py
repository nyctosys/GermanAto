"""Additive estimate / quote fields. Safe to re-run."""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import engine
import app.models  # noqa: F401

COLUMNS = {
    "invoice": {
        "approval_state": "VARCHAR(30) DEFAULT 'draft'",
        "expected_duration_hours": "DOUBLE PRECISION NULL",
        "expected_completion_at": "TIMESTAMP NULL",
        "required_advance": "DOUBLE PRECISION DEFAULT 0",
        "advance_policy_mode": "VARCHAR(20)",
        "advance_policy_value": "DOUBLE PRECISION NULL",
    },
}


def _existing(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def main() -> int:
    print("Migrating estimate fields…")
    for table, cols in COLUMNS.items():
        existing = _existing(table)
        if not existing:
            print(f"  skip {table}")
            continue
        with engine.begin() as conn:
            for name, ddl in cols.items():
                if name in existing:
                    continue
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
                print(f"  + {table}.{name}")
    # Backfill quotes to draft if null
    if "approval_state" in _existing("invoice"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE invoice SET approval_state = 'draft' "
                    "WHERE approval_state IS NULL AND LOWER(type_of) IN ('quote','quotation','estimate')"
                )
            )
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
