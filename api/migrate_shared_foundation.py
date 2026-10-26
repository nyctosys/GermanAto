"""
Additive shared-data foundation migration.

Safe to re-run. Adds permanent codes/document numbers, actor columns,
gate_pass table, and backfills codes from existing integer ids.
Does not rewrite or drop data.
"""

from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.db import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.document_numbers import (
    car_code,
    cash_document_no,
    customer_code,
    expense_document_no,
    invoice_document_no,
    po_document_no,
    repair_order_document_no,
    vendor_code,
)

COLUMNS: dict[str, dict[str, str]] = {
    "customer": {
        "code": "VARCHAR(20)",
        "created_by_user": "VARCHAR(80)",
        "updated_by_user": "VARCHAR(80)",
    },
    "car": {
        "code": "VARCHAR(20)",
        "created_by_user": "VARCHAR(80)",
        "updated_by_user": "VARCHAR(80)",
    },
    "invoice": {
        "document_no": "VARCHAR(40)",
    },
    "repair_order": {
        "document_no": "VARCHAR(40)",
    },
    "expense": {
        "document_no": "VARCHAR(40)",
        "created_by_user": "VARCHAR(80)",
        "updated_by_user": "VARCHAR(80)",
    },
    "cash_received": {
        "document_no": "VARCHAR(40)",
        "created_by_user": "VARCHAR(80)",
        "updated_by_user": "VARCHAR(80)",
    },
    "purchase_orders": {
        "document_no": "VARCHAR(40)",
        "updated_by_user": "VARCHAR(80)",
    },
    "vendors": {
        "code": "VARCHAR(20)",
        "created_by_user": "VARCHAR(80)",
        "updated_by_user": "VARCHAR(80)",
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
            continue
        with engine.begin() as conn:
            for name, ddl in cols.items():
                if name in existing:
                    continue
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
                print(f"  + {table}.{name}")


def _unique_index(table: str, column: str, index_name: str) -> None:
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
                text(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS {index_name} '
                    f'ON "{table}" ({column}) WHERE {column} IS NOT NULL'
                )
            )
        print(f"  + unique index {index_name}")
    except Exception as exc:
        # Fallback without partial index (SQLite / older PG)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(f'CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON "{table}" ({column})')
                )
            print(f"  + unique index {index_name} (non-partial)")
        except Exception as exc2:
            print(f"  (skip index {index_name}: {exc} / {exc2})")


def _backfill_sql(table: str, id_col: str, code_col: str, formatter) -> int:
    """Backfill codes with core columns only so missing ORM cols cannot block."""
    existing = _existing_columns(table)
    if code_col not in existing or id_col not in existing:
        return 0
    n = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text(f'SELECT {id_col} FROM "{table}" WHERE {code_col} IS NULL')
        ).fetchall()
        for (row_id,) in rows:
            conn.execute(
                text(
                    f'UPDATE "{table}" SET {code_col} = :code '
                    f'WHERE {id_col} = :id AND {code_col} IS NULL'
                ),
                {"code": formatter(row_id), "id": row_id},
            )
            n += 1
    return n


def _backfill() -> None:
    n = 0
    n += _backfill_sql("customer", "id", "code", customer_code)
    n += _backfill_sql("car", "id", "code", car_code)
    n += _backfill_sql("vendors", "id", "code", vendor_code)

    db = SessionLocal()
    try:
        from app.models import (
            CashReceived,
            Expense,
            Invoice,
            PurchaseOrder,
            RepairOrder,
        )

        for inv in db.query(Invoice.id, Invoice.type_of).filter(Invoice.document_no.is_(None)).all():
            inv_id, type_of = inv[0], inv[1]
            db.execute(
                text(
                    "UPDATE invoice SET document_no = :d WHERE id = :id AND document_no IS NULL"
                ),
                {"d": invoice_document_no(inv_id, type_of=type_of), "id": inv_id},
            )
            n += 1
        for (ro_id,) in db.query(RepairOrder.id).filter(RepairOrder.document_no.is_(None)).all():
            db.execute(
                text(
                    "UPDATE repair_order SET document_no = :d WHERE id = :id AND document_no IS NULL"
                ),
                {"d": repair_order_document_no(ro_id), "id": ro_id},
            )
            n += 1
        for (e_id,) in db.query(Expense.id).filter(Expense.document_no.is_(None)).all():
            db.execute(
                text(
                    "UPDATE expense SET document_no = :d WHERE id = :id AND document_no IS NULL"
                ),
                {"d": expense_document_no(e_id), "id": e_id},
            )
            n += 1
        for (cr_id,) in db.query(CashReceived.id).filter(CashReceived.document_no.is_(None)).all():
            db.execute(
                text(
                    "UPDATE cash_received SET document_no = :d WHERE id = :id AND document_no IS NULL"
                ),
                {"d": cash_document_no(cr_id), "id": cr_id},
            )
            n += 1
        for (po_id,) in db.query(PurchaseOrder.id).filter(PurchaseOrder.document_no.is_(None)).all():
            db.execute(
                text(
                    "UPDATE purchase_orders SET document_no = :d WHERE id = :id AND document_no IS NULL"
                ),
                {"d": po_document_no(po_id), "id": po_id},
            )
            n += 1
        db.commit()
        print(f"  backfilled {n} codes/document numbers")
    except Exception as exc:
        db.rollback()
        print(f"  (backfill error: {exc})")
        raise
    finally:
        db.close()


def main() -> int:
    print("Creating tables (gate_pass, etc.) if needed...")
    Base.metadata.create_all(bind=engine)

    print("Adding shared foundation columns...")
    _add_columns()

    print("Ensuring unique indexes on codes...")
    _unique_index("customer", "code", "uq_customer_code")
    _unique_index("car", "code", "uq_car_code")
    _unique_index("vendors", "code", "uq_vendor_code")
    _unique_index("invoice", "document_no", "uq_invoice_document_no")
    _unique_index("repair_order", "document_no", "uq_ro_document_no")
    _unique_index("expense", "document_no", "uq_expense_document_no")
    _unique_index("cash_received", "document_no", "uq_cash_document_no")
    _unique_index("purchase_orders", "document_no", "uq_po_document_no")
    _unique_index("gate_pass", "document_no", "uq_gate_pass_document_no")

    print("Backfilling permanent codes from existing ids...")
    _backfill()

    print("Shared data foundation migration complete.")
    print(
        "Schema summary:\n"
        "  customer.code, car.code, vendors.code\n"
        "  invoice/repair_order/expense/cash_received/purchase_orders.document_no\n"
        "  created_by_user/updated_by_user on customer, car, expense, cash, vendors\n"
        "  gate_pass table (direction, customer_id, car_id, visit_id, repair_order_id)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
