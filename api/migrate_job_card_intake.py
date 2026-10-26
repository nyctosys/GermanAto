"""
Additive Job Card / Vehicle Intake fields + RO display title.

Safe to re-run. Does not drop or rewrite existing codes/history.
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import engine
import app.models  # noqa: F401
from app.document_numbers import job_card_document_no

COLUMNS: dict[str, dict[str, str]] = {
    "job_cards": {
        "document_no": "VARCHAR(40)",
        "priority": "VARCHAR(20) DEFAULT 'normal'",
        "expected_completion_at": "TIMESTAMP NULL",
        "intake_at": "TIMESTAMP NULL",
        "worker_id": "INTEGER NULL",
        "team_name": "VARCHAR(120)",
        "problem_description": "TEXT",
        "inspection_notes": "TEXT",
        "odometer": "VARCHAR(50)",
        "fuel_level": "VARCHAR(40)",
    },
    "repair_order": {
        "display_title": "VARCHAR(255)",
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


def _backfill_job_card_nos() -> None:
    if "document_no" not in _existing_columns("job_cards"):
        return
    n = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id FROM job_cards WHERE document_no IS NULL")
        ).fetchall()
        for (row_id,) in rows:
            conn.execute(
                text(
                    "UPDATE job_cards SET document_no = :d "
                    "WHERE id = :id AND document_no IS NULL"
                ),
                {"d": job_card_document_no(row_id), "id": row_id},
            )
            n += 1
    print(f"  backfilled {n} job card document numbers")


def _index() -> None:
    if "document_no" not in _existing_columns("job_cards"):
        return
    insp = inspect(engine)
    indexes = {ix["name"] for ix in insp.get_indexes("job_cards")}
    if "uq_job_cards_document_no" in indexes:
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_job_cards_document_no "
                    "ON job_cards (document_no) WHERE document_no IS NOT NULL"
                )
            )
        print("  + unique index uq_job_cards_document_no")
    except Exception as exc:
        print(f"  ! index uq_job_cards_document_no: {exc}")


def main() -> int:
    print("Migrating job card intake fields…")
    _add_columns()
    _backfill_job_card_nos()
    _index()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
