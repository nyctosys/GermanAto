"""Additive Repair Execution columns + tables. Safe to re-run."""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.db import Base, engine
import app.models as models  # noqa: F401 — register metadata


EXEC_COLUMNS: dict[str, dict[str, str]] = {
    "repair_order": {
        "due_at": "TIMESTAMP NULL",
        "submitted_for_qc_at": "TIMESTAMP NULL",
        "labour_cost_total": "DOUBLE PRECISION DEFAULT 0",
        "parts_cost_total": "DOUBLE PRECISION DEFAULT 0",
    },
    "repair_order_part": {
        "approval_status": "VARCHAR(20) DEFAULT 'approved'",
        "unit_cost": "DOUBLE PRECISION NULL",
    },
    "repair_order_labour": {
        "assigned_worker_id": "INTEGER NULL",
        "approval_status": "VARCHAR(20) DEFAULT 'approved'",
        "std_hours": "DOUBLE PRECISION NULL",
        "actual_hours": "DOUBLE PRECISION DEFAULT 0",
        "labour_rate": "DOUBLE PRECISION NULL",
        "labour_cost": "DOUBLE PRECISION DEFAULT 0",
        "started_at": "TIMESTAMP NULL",
        "paused_at": "TIMESTAMP NULL",
        "completed_at": "TIMESTAMP NULL",
        "deadline_at": "TIMESTAMP NULL",
        "line_notes": "TEXT NULL",
    },
}


def _existing_columns(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def add_columns() -> None:
    for table, cols in EXEC_COLUMNS.items():
        existing = _existing_columns(table)
        if not existing:
            print(f"  (skip {table}: table missing)")
            continue
        with engine.begin() as conn:
            for name, ddl in cols.items():
                if name in existing:
                    continue
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
                print(f"  + {table}.{name}")


def create_new_tables() -> None:
    # create_all is additive for missing tables only
    Base.metadata.create_all(
        bind=engine,
        tables=[
            models.RepairTimeEntry.__table__,
            models.RepairFault.__table__,
        ],
    )
    print("  ensured repair_time_entries + repair_faults")


def run() -> int:
    print("Repair Execution migration...")
    add_columns()
    create_new_tables()
    print("Done.")
    return 0


if __name__ == "__main__":
    run()
