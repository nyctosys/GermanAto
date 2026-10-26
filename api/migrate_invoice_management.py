"""
Additive invoice management tables: customer_ledger, customer_credit_notes.

Safe to re-run. Existing invoice data keeps working.
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import Base, engine
import app.models  # noqa: F401


def main() -> int:
    print("migrate_invoice_management …")
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    Base.metadata.create_all(
        bind=engine,
        tables=[
            app.models.CustomerLedger.__table__,
            app.models.CustomerCreditNote.__table__,
        ],
    )
    after = set(inspect(engine).get_table_names())
    for name in sorted(after - existing):
        print(f"  + table {name}")
    if "customer_ledger" in after and "customer_ledger" not in existing:
        print("  customer_ledger ready")
    if "customer_credit_notes" in after and "customer_credit_notes" not in existing:
        print("  customer_credit_notes ready")
    # Helpful index for duplicate invoice-per-RO checks (non-unique; app enforces)
    if "invoice" in after:
        with engine.begin() as conn:
            try:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_invoice_ro_type "
                        "ON invoice (repair_order_id, type_of)"
                    )
                )
                print("  + index ix_invoice_ro_type")
            except Exception as exc:  # noqa: BLE001
                print(f"  ! index: {exc}")
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
