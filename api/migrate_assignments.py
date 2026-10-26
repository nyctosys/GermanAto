"""Additive worker assignment / scheduling tables + skills column. Safe to re-run."""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import Base, engine
from app.models import WorkerLeave, WorkAssignment, WorkTimeEntry  # noqa: F401


def _columns(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def main() -> int:
    print("Migrating worker assignment / scheduling…")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            WorkerLeave.__table__,
            WorkAssignment.__table__,
            WorkTimeEntry.__table__,
        ],
    )
    print("  tables worker_leave / work_assignments / work_time_entries ensured")

    cols = _columns("workers")
    if cols and "skills_json" not in cols:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE "workers" ADD COLUMN skills_json TEXT'))
        print("  + workers.skills_json")

    # Helpful indexes (IF NOT EXISTS)
    for ddl in (
        "CREATE INDEX IF NOT EXISTS ix_work_assignments_worker_status "
        "ON work_assignments (worker_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_work_assignments_deadline "
        "ON work_assignments (deadline_at)",
        "CREATE INDEX IF NOT EXISTS ix_worker_leave_worker_dates "
        "ON worker_leave (worker_id, start_date, end_date)",
        "CREATE INDEX IF NOT EXISTS ix_work_time_worker "
        "ON work_time_entries (worker_id)",
    ):
        try:
            with engine.begin() as conn:
                conn.execute(text(ddl))
        except Exception as exc:
            print(f"  ! index: {exc}")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
