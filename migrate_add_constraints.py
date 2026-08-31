"""Database constraints: keep the historical data, stop repeating its mistakes.

Everything recorded before the cutoff is legacy. It stays exactly as it is and
is exempted from the rules it would fail - notably the 313 invoices marked
`paid` with no payment amount ever recorded. From the cutoff onwards the
database itself refuses those entries, so the rule holds no matter which code
path (or hand-written SQL) tries it.

Requires MySQL 8.0.16+ for CHECK enforcement. MySQL 5.7 parses CHECK and then
silently ignores it, so running this against 5.7 gives false confidence - the
script refuses to run there.

    DATABASE_URL="mysql+pymysql://user:pass@localhost/germanato_db" \
        python3 migrate_add_constraints.py [--apply]

Without --apply it reports which constraints would be added and what, if
anything, in the current data would block them.
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

# Anything created before this is legacy: preserved untouched and exempt.
LEGACY_CUTOFF = "2026-09-01"

# Amount owed on an invoice, written the same way as invoice_amount_due() in
# routes.py. Kept as one string so the constraints cannot drift from each other.
DUE = ("net_total + CASE WHEN include_tax THEN COALESCE(tax_amount,0) ELSE 0 END "
       "- COALESCE(discount,0)")
PAID = "COALESCE(advance,0) + COALESCE(paid_amount,0)"

# (table, constraint name, rule, the query that finds rows the rule would reject)
CHECKS = [
    # --- apply to all rows: the existing data already satisfies these ---
    ("invoice", "chk_invoice_amounts_non_negative",
     "net_total >= 0 AND COALESCE(advance,0) >= 0 AND COALESCE(paid_amount,0) >= 0 "
     "AND COALESCE(discount,0) >= 0 AND COALESCE(tax_amount,0) >= 0",
     "SELECT COUNT(*) FROM invoice WHERE net_total<0 OR COALESCE(advance,0)<0 "
     "OR COALESCE(paid_amount,0)<0 OR COALESCE(discount,0)<0 OR COALESCE(tax_amount,0)<0"),

    # Status vocabulary is type-dependent: invoices are paid/unpaid/partially_paid,
    # quotes are pending/approved. Mixing them is what let 'complete' vs 'completed'
    # style drift happen elsewhere.
    ("invoice", "chk_invoice_status_vocabulary",
     "(type_of = 'invoice' AND status IN ('unpaid','partially_paid','paid')) "
     "OR (type_of = 'quote' AND status IN ('pending','approved'))",
     "SELECT COUNT(*) FROM invoice WHERE NOT ("
     "(type_of='invoice' AND status IN ('unpaid','partially_paid','paid')) "
     "OR (type_of='quote' AND status IN ('pending','approved')))"),

    ("repair_order", "chk_repair_order_status_vocabulary",
     "current_status IN ('received','diagnosis','repair','testing','complete')",
     "SELECT COUNT(*) FROM repair_order WHERE current_status NOT IN "
     "('received','diagnosis','repair','testing','complete')"),

    # --- legacy-exempt: historical rows break these and must stay as they are ---
    ("invoice", "chk_invoice_no_overpayment",
     f"created_at < '{LEGACY_CUTOFF}' OR type_of <> 'invoice' OR {PAID} <= ({DUE}) + 0.01",
     f"SELECT COUNT(*) FROM invoice WHERE created_at >= '{LEGACY_CUTOFF}' "
     f"AND type_of='invoice' AND {PAID} > ({DUE}) + 0.01"),

    # The mistake this whole exercise is about: marked paid, money never recorded.
    ("invoice", "chk_invoice_paid_requires_payment",
     f"created_at < '{LEGACY_CUTOFF}' OR status <> 'paid' OR {PAID} >= ({DUE}) - 0.01",
     f"SELECT COUNT(*) FROM invoice WHERE created_at >= '{LEGACY_CUTOFF}' "
     f"AND status='paid' AND {PAID} < ({DUE}) - 0.01"),
]

UNIQUES = [
    ("vendors", "uq_vendor_identity", "name, company_name, phone",
     "SELECT COUNT(*) FROM (SELECT 1 FROM vendors GROUP BY name,company_name,phone "
     "HAVING COUNT(*)>1) d"),
]


def existing_constraints(conn, table):
    rows = conn.execute(text(
        "SELECT constraint_name FROM information_schema.table_constraints "
        "WHERE table_schema = DATABASE() AND table_name = :t"), {"t": table})
    return {r[0] for r in rows}


def main():
    with app.app_context():
        with db.engine.begin() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar() or ""
            major_minor = version.split("-")[0]
            parts = [int(p) for p in major_minor.split(".")[:3] if p.isdigit()]
            if parts < [8, 0, 16]:
                sys.exit(
                    f"MySQL {version} does not enforce CHECK constraints "
                    "(needs 8.0.16+). Refusing to run - it would report success "
                    "while enforcing nothing."
                )
            print(f"MySQL {version} - CHECK constraints are enforced.\n")
            print(f"Legacy cutoff: rows created before {LEGACY_CUTOFF} are exempt.\n")

            blocked = False

            for table, name, rule, probe in CHECKS:
                have = existing_constraints(conn, table)
                if name in have:
                    print(f"  = {table}.{name} already present")
                    continue
                violations = conn.execute(text(probe)).scalar()
                if violations:
                    blocked = True
                    print(f"  ! {table}.{name} BLOCKED by {violations} existing row(s)")
                    continue
                if APPLY:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({rule})"))
                    print(f"  + {table}.{name} added")
                else:
                    print(f"  ~ {table}.{name} would be added (0 violations)")

            for table, name, cols, probe in UNIQUES:
                have = existing_constraints(conn, table)
                if name in have:
                    print(f"  = {table}.{name} already present")
                    continue
                violations = conn.execute(text(probe)).scalar()
                if violations:
                    blocked = True
                    print(f"  ! {table}.{name} BLOCKED by {violations} duplicate group(s)")
                    continue
                if APPLY:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD CONSTRAINT {name} UNIQUE ({cols})"))
                    print(f"  + {table}.{name} added")
                else:
                    print(f"  ~ {table}.{name} would be added (0 violations)")

            print()
            if blocked:
                print("Some constraints were skipped - clean the rows listed above first.")
            if not APPLY:
                print("Dry run - nothing written. Re-run with --apply to commit.")


if __name__ == "__main__":
    main()
