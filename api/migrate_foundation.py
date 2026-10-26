"""
Additive foundation migration for existing PostgreSQL databases.

Safe to re-run. Creates branch/attachments/idempotency tables, seeds default
branch, and adds branch_id / version / deleted_at / created_by / updated_by /
audit columns where missing. Does not rewrite money columns.
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.foundation.branch import DEFAULT_BRANCH_ID, DEFAULT_BRANCH_NAME, ensure_default_branch

FOUNDATION_TABLES = [
    "user",
    "invoice",
    "invoice_item",
    "invoice_labour",
    "inventory",
    "customer",
    "car",
    "repair_order",
    "repair_order_part",
    "repair_order_labour",
    "expense",
    "cash_received",
    "financial_periods",
    "whats_app_notification",
    "vendors",
    "vendor_ledger",
    "purchase_orders",
    "workers",
    "salary_advances",
    "payroll_runs",
    "attendance_records",
    "zkteco_devices",
    "departments",
    "categories",
    "inventory_transactions",
    "visits",
    "visit_inspection_items",
    "inspection_templates",
    "car_ownership",
    "labour_codes",
    "job_cards",
    "job_card_lines",
    "approval_tokens",
    "quote_line_approvals",
    "customer_deposits",
    "variations",
    "variation_lines",
    "qc_signoffs",
    "gate_passes",
]

FOUNDATION_COLUMNS = {
    "branch_id": f"VARCHAR(8) DEFAULT '{DEFAULT_BRANCH_ID}'",
    "version": "INTEGER DEFAULT 1",
    "deleted_at": "TIMESTAMP NULL",
}

APP_LOG_COLUMNS = {
    "old_value": "TEXT NULL",
    "new_value": "TEXT NULL",
    "reason": "VARCHAR(255) NULL",
    "branch_id": f"VARCHAR(8) DEFAULT '{DEFAULT_BRANCH_ID}'",
}


def _existing_columns(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add_columns(table: str, columns: dict[str, str]) -> None:
    existing = _existing_columns(table)
    if not existing and table not in ("branch", "attachments", "idempotency_keys"):
        # Table missing entirely — create_all will handle on next boot
        return
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name in existing:
                continue
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
            print(f"  + {table}.{name}")


def _widen_user_role() -> None:
    existing = _existing_columns("user")
    if not existing:
        return
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE "user" ALTER COLUMN role TYPE VARCHAR(40)'))
        print("  ~ user.role -> VARCHAR(40)")


def main() -> int:
    print("Creating new tables (if needed)...")
    Base.metadata.create_all(bind=engine)

    print("Seeding default branch...")
    db = SessionLocal()
    try:
        ensure_default_branch(db)
        db.commit()
        print(f"  default branch {DEFAULT_BRANCH_ID} ({DEFAULT_BRANCH_NAME})")
    finally:
        db.close()

    print("Adding foundation columns...")
    for table in FOUNDATION_TABLES:
        _add_columns(table, FOUNDATION_COLUMNS)

    print("Extending app_logs...")
    _add_columns("app_logs", APP_LOG_COLUMNS)

    print("Widening user.role...")
    try:
        _widen_user_role()
    except Exception as exc:
        print(f"  (skip role widen: {exc})")

    # Backfill null branch_id
    with engine.begin() as conn:
        for table in FOUNDATION_TABLES:
            cols = _existing_columns(table)
            if "branch_id" not in cols:
                continue
            conn.execute(
                text(
                    f"UPDATE \"{table}\" SET branch_id = :bid WHERE branch_id IS NULL"
                ),
                {"bid": DEFAULT_BRANCH_ID},
            )
        if "branch_id" in _existing_columns("app_logs"):
            conn.execute(
                text(
                    "UPDATE app_logs SET branch_id = :bid WHERE branch_id IS NULL"
                ),
                {"bid": DEFAULT_BRANCH_ID},
            )

    print("Adding CHECK constraints (non-negative money/qty)...")
    _add_check_constraints()

    print("Seeding workshop settings defaults...")
    db = SessionLocal()
    try:
        from app.foundation.settings import ensure_default_settings

        ensure_default_settings(db)
        db.commit()
        print("  app_settings defaults ready")
    except Exception as exc:
        db.rollback()
        print(f"  (skip settings seed: {exc})")
    finally:
        db.close()

    print("Running pipeline migration...")
    try:
        from migrate_pipeline import run as run_pipeline

        run_pipeline()
    except Exception as exc:
        print(f"  (skip pipeline migrate: {exc})")

    print("Foundation migration complete.")
    return 0


CHECK_CONSTRAINTS = [
    ("expense", "ck_expense_amount_nonneg", "amount >= 0"),
    ("cash_received", "ck_cash_received_amount_nonneg", "amount >= 0"),
    ("invoice_item", "ck_invoice_item_qty_nonneg", "quantity >= 0"),
    ("invoice_item", "ck_invoice_item_price_nonneg", "price >= 0"),
    ("invoice_labour", "ck_invoice_labour_price_nonneg", "price >= 0"),
    ("inventory", "ck_inventory_qty_nonneg", "quantity >= 0"),
    ("inventory", "ck_inventory_price_nonneg", "price >= 0"),
    ("inventory", "ck_inventory_qty_reserved_nonneg", "qty_reserved >= 0"),
    ("purchase_orders", "ck_po_qty_nonneg", "quantity >= 0"),
    ("purchase_orders", "ck_po_rate_nonneg", "rate >= 0"),
    ("purchase_orders", "ck_po_amount_nonneg", "amount >= 0"),
    ("customer_deposits", "ck_deposit_amount_nonneg", "amount >= 0"),
    ("labour_codes", "ck_labour_rate_nonneg", "rate >= 0"),
    ("labour_codes", "ck_labour_hours_nonneg", "standard_hours >= 0"),
]


def _add_check_constraints() -> None:
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


if __name__ == "__main__":
    sys.exit(main())
