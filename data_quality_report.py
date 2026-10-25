"""Data quality report - read-only.

Counts the kinds of mistakes that accumulate in free-text fields: unusable phone
numbers, placeholder addresses, vehicle details typed into the wrong column, and
inventory items entered twice under slightly different spellings so their stock
is split across two records.

Writes nothing. Run it before and after a cleanup to see what moved.

    DATABASE_URL="mysql+pymysql://user:pass@localhost/germanato_db" \\
        python3 data_quality_report.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("DATABASE_URL"):
    sys.exit("Set DATABASE_URL first.")

from sqlalchemy import text                                # noqa: E402
from app import app, db                                    # noqa: E402

# Values people type when a field is required but they have nothing to enter.
PLACEHOLDERS = ("n/a", "na", "-", ".", "none", "null", "xx", "x", "abc",
                "test", "lahore", "0", "00", "000")

PLACEHOLDER_SQL = ",".join(f"'{p}'" for p in PLACEHOLDERS)


def section(title):
    print(f"\n{title}\n{'-' * len(title)}")


def row(label, value, of=None, flag_at=None):
    pct = f"  ({value / of * 100:4.1f}%)" if of else ""
    mark = ""
    if flag_at is not None and of and value / of >= flag_at:
        mark = "   <-- worth fixing"
    print(f"  {label:<38} {value:>6,}{pct}{mark}")


def main():
    with app.app_context():
        conn = db.engine.connect()
        q = lambda s: conn.execute(text(s)).fetchall()
        one = lambda s: conn.execute(text(s)).scalar()

        section("PHONE NUMBERS")
        for tbl, col in (("customer", "phone"), ("invoice", "customer_phone"),
                         ("repair_order", "customer_phone")):
            total = one(f"SELECT COUNT(*) FROM {tbl}")
            bad = one(f"""
                SELECT COUNT(*) FROM {tbl}
                WHERE CHAR_LENGTH(REGEXP_REPLACE(COALESCE({col},''),'[^0-9]','')) < 10
            """)
            row(f"{tbl}: unusable (under 10 digits)", bad, total, flag_at=.05)

        section("ADDRESSES")
        for tbl, col in (("customer", "address"), ("invoice", "customer_address"),
                         ("repair_order", "customer_address")):
            total = one(f"SELECT COUNT(*) FROM {tbl}")
            junk = one(f"""
                SELECT COUNT(*) FROM {tbl}
                WHERE LOWER(TRIM(COALESCE({col},''))) IN ({PLACEHOLDER_SQL})
                   OR CHAR_LENGTH(TRIM(COALESCE({col},''))) < 5
            """)
            row(f"{tbl}: placeholder or too short", junk, total, flag_at=.5)

        section("VEHICLES")
        cars = one("SELECT COUNT(*) FROM car")
        row("cars on file", cars)
        row("duplicate number plates", one("""
            SELECT COUNT(*) FROM (SELECT 1 FROM car GROUP BY plate_no HAVING COUNT(*)>1) d"""))
        row("VIN present but not 17 characters", one("""
            SELECT COUNT(*) FROM car
            WHERE CHAR_LENGTH(REGEXP_REPLACE(COALESCE(vin,''),'[^A-Za-z0-9]','')) NOT IN (0,17)"""), cars, flag_at=.2)
        row("distinct values in 'make'", one("SELECT COUNT(DISTINCT make) FROM car"))
        row("  (a real brand list is ~15)", 0)
        row("mileage containing non-digits", one("""
            SELECT COUNT(*) FROM invoice
            WHERE TRIM(COALESCE(customer_mileage,''))<>''
              AND NOT customer_mileage REGEXP '^[0-9]+$'"""))

        section("CUSTOMERS")
        cust = one("SELECT COUNT(*) FROM customer")
        row("customer records", cust)
        row("duplicate phone groups", one("""
            SELECT COUNT(*) FROM (
              SELECT 1 FROM customer
              WHERE CHAR_LENGTH(REGEXP_REPLACE(COALESCE(phone,''),'[^0-9]','')) >= 10
              GROUP BY REGEXP_REPLACE(phone,'[^0-9]','') HAVING COUNT(*)>1) d"""))

        section("INVENTORY NAMES")
        items = one("SELECT COUNT(*) FROM inventory")
        row("items", items)
        row("names with repeated spaces", one(
            "SELECT COUNT(*) FROM inventory WHERE name REGEXP '  '"), items, flag_at=.1)
        row("names not trimmed", one(
            "SELECT COUNT(*) FROM inventory WHERE name <> TRIM(name)"))
        dup = q("""
            SELECT UPPER(REGEXP_REPLACE(name,'[^A-Za-z0-9]','')) k,
                   COUNT(*) n, SUM(quantity) qty,
                   GROUP_CONCAT(name ORDER BY name SEPARATOR ' | ') variants
            FROM inventory GROUP BY k HAVING COUNT(*) > 1 ORDER BY qty DESC""")
        row("same part entered more than once", len(dup))
        row("  stock units split across them", sum(int(d[2] or 0) for d in dup))
        if dup:
            print("\n  Split stock - these are one part each:")
            for _, n, qty, variants in dup[:10]:
                print(f"    {qty:>4} units over {n}:  {variants[:88]}")

        conn.close()
        print("\nRead-only: nothing was changed.")


if __name__ == "__main__":
    main()
