"""Link cash receipts to the invoice they settle.

`cash_received` recorded Rs 50.8M of payments with no reference to any invoice -
just a free-text description - so nothing could answer "has this job been paid
for?" without a human reading prose. This adds the missing link.

The column is nullable by design, for two reasons:

  * genuine non-invoice income exists (scrap sales, refunds, owner deposits)
  * the 765 receipts taken before this column existed cannot be recovered.
    Their descriptions carry no invoice reference - 0 with a #number, 3 that
    mention "invoice" at all - and matching on amount + date leaves only 67
    with a single candidate against 675 with none. Guessing at money linkage
    would be worse than leaving it blank, so historical rows stay NULL and
    remain legacy.

    DATABASE_URL="mysql+pymysql://user:pass@localhost/germanato_db" \\
        python3 migrate_cash_received_invoice_link.py [--apply]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("DATABASE_URL"):
    sys.exit("Set DATABASE_URL first.")

APPLY = "--apply" in sys.argv

from sqlalchemy import text                                # noqa: E402
from app import app, db                                    # noqa: E402

STEPS = [
    ("column", "invoice_id",
     "ALTER TABLE cash_received ADD COLUMN invoice_id INT NULL"),
    ("index", "idx_cash_received_invoice_id",
     "CREATE INDEX idx_cash_received_invoice_id ON cash_received(invoice_id)"),
    # The FK is what actually guarantees a receipt can never point at an invoice
    # that does not exist. ON DELETE SET NULL keeps the cash record - the money
    # was still received even if the invoice is later removed.
    ("fk", "fk_cash_received_invoice",
     "ALTER TABLE cash_received ADD CONSTRAINT fk_cash_received_invoice "
     "FOREIGN KEY (invoice_id) REFERENCES invoice(id) ON DELETE SET NULL"),
]


def has_column(conn, table, column):
    return conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
        "AND table_name=:t AND column_name=:c"), {"t": table, "c": column}).scalar() > 0


def has_index(conn, table, name):
    return conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=DATABASE() "
        "AND table_name=:t AND index_name=:n"), {"t": table, "n": name}).scalar() > 0


def has_constraint(conn, table, name):
    return conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema=DATABASE() "
        "AND table_name=:t AND constraint_name=:n"), {"t": table, "n": name}).scalar() > 0


EXISTS = {"column": has_column, "index": has_index, "fk": has_constraint}


def main():
    with app.app_context():
        with db.engine.begin() as conn:
            for kind, name, ddl in STEPS:
                if EXISTS[kind](conn, "cash_received", name):
                    print(f"  = {name} already present")
                    continue
                if APPLY:
                    conn.execute(text(ddl))
                    print(f"  + {name} added")
                else:
                    print(f"  ~ {name} would be added")

            receipts = conn.execute(text("SELECT COUNT(*) FROM cash_received")).scalar()
            if has_column(conn, "cash_received", "invoice_id"):
                linked = conn.execute(text(
                    "SELECT COUNT(*) FROM cash_received WHERE invoice_id IS NOT NULL")).scalar()
                print(f"\n  receipts: {receipts} total, {linked} linked, "
                      f"{receipts - linked} legacy (unlinked)")

        if not APPLY:
            print("\nDry run - nothing written. Re-run with --apply to commit.")


if __name__ == "__main__":
    main()
