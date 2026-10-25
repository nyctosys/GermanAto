"""Link existing invoices and repair orders to their customer and car.

Both documents stored the customer and vehicle as text only. That text is
correct and stays - a document records what was true when it was written - but
with no id, "show me this customer's cars" had to match on names that get
retyped and misspelled, and a car added while no customer was selected stayed
orphaned forever.

This adds the ids and fills them in for existing rows, using exactly the same
matching rules the application now uses at save time, so the two cannot drift.

    DATABASE_URL="mysql+pymysql://user:pass@localhost/germanato_db" \\
        python3 migrate_customer_car_links.py [--apply]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("DATABASE_URL"):
    sys.exit("Set DATABASE_URL first.")

APPLY = "--apply" in sys.argv

from sqlalchemy import text                                     # noqa: E402
from app import app, db                                         # noqa: E402
from models import Invoice, RepairOrder, Car                    # noqa: E402
from document_links import resolve_customer, resolve_car, adopt_orphan_car  # noqa: E402

COLUMNS = [
    ("invoice", "customer_id", "ALTER TABLE invoice ADD COLUMN customer_id INT NULL"),
    ("invoice", "car_id", "ALTER TABLE invoice ADD COLUMN car_id INT NULL"),
    ("repair_order", "customer_id", "ALTER TABLE repair_order ADD COLUMN customer_id INT NULL"),
    ("repair_order", "car_id", "ALTER TABLE repair_order ADD COLUMN car_id INT NULL"),
]

INDEXES = [
    ("invoice", "idx_invoice_customer_id", "CREATE INDEX idx_invoice_customer_id ON invoice(customer_id)"),
    ("invoice", "idx_invoice_car_id", "CREATE INDEX idx_invoice_car_id ON invoice(car_id)"),
    ("repair_order", "idx_repair_order_customer_id", "CREATE INDEX idx_repair_order_customer_id ON repair_order(customer_id)"),
    ("repair_order", "idx_repair_order_car_id", "CREATE INDEX idx_repair_order_car_id ON repair_order(car_id)"),
]

# SET NULL, never CASCADE: deleting a customer must not delete their invoices.
FKS = [
    ("invoice", "fk_invoice_customer",
     "ALTER TABLE invoice ADD CONSTRAINT fk_invoice_customer FOREIGN KEY (customer_id) "
     "REFERENCES customer(id) ON DELETE SET NULL"),
    ("invoice", "fk_invoice_car",
     "ALTER TABLE invoice ADD CONSTRAINT fk_invoice_car FOREIGN KEY (car_id) "
     "REFERENCES car(id) ON DELETE SET NULL"),
    ("repair_order", "fk_repair_order_customer",
     "ALTER TABLE repair_order ADD CONSTRAINT fk_repair_order_customer FOREIGN KEY (customer_id) "
     "REFERENCES customer(id) ON DELETE SET NULL"),
    ("repair_order", "fk_repair_order_car",
     "ALTER TABLE repair_order ADD CONSTRAINT fk_repair_order_car FOREIGN KEY (car_id) "
     "REFERENCES car(id) ON DELETE SET NULL"),
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


def add_schema():
    with db.engine.begin() as conn:
        for table, column, ddl in COLUMNS:
            if has_column(conn, table, column):
                print(f"  = {table}.{column} already present")
            elif APPLY:
                conn.execute(text(ddl)); print(f"  + {table}.{column} added")
            else:
                print(f"  ~ {table}.{column} would be added")

        if not APPLY:
            return False  # nothing further can run until the columns exist

        for table, name, ddl in INDEXES:
            if not has_index(conn, table, name):
                conn.execute(text(ddl)); print(f"  + {name}")
        for table, name, ddl in FKS:
            if not has_constraint(conn, table, name):
                conn.execute(text(ddl)); print(f"  + {name}")
        return True


def _customer(customer_id):
    from models import Customer
    return db.session.get(Customer, customer_id)


def backfill(model, label):
    """Match existing rows, using the application's own rules."""
    rows = model.query.all()
    linked_customer = linked_car = adopted = 0

    for row in rows:
        if row.customer_id is None:
            customer = resolve_customer(None, row.customer_name, row.customer_phone)
            if customer:
                row.customer_id = customer.id
                linked_customer += 1

        if row.car_id is None:
            car = resolve_car(None, row.customer_reg_no, row.customer_vin, row.customer_id)
            if car:
                row.car_id = car.id
                linked_car += 1
                # A document naming both claims the car for that customer.
                if row.customer_id and adopt_orphan_car(car, _customer(row.customer_id)):
                    adopted += 1

    unmatched = sum(1 for r in rows if r.customer_id is None)
    print(f"\n  {label}: {len(rows)} rows")
    print(f"    newly linked to a customer : {linked_customer}")
    print(f"    newly linked to a car      : {linked_car}")
    print(f"    orphan cars adopted        : {adopted}")
    print(f"    still with no customer     : {unmatched}"
          f"{'   <-- named a customer that has no record' if unmatched else ''}")


def main():
    with app.app_context():
        ready = add_schema()
        if not ready:
            print("\nDry run - nothing written. Re-run with --apply to add the "
                  "columns and backfill the links.")
            return

        backfill(Invoice, "invoices")
        backfill(RepairOrder, "repair orders")

        db.session.commit()
        orphans = Car.query.filter(Car.customer_id.is_(None)).count()
        print(f"\n  cars still with no owner: {orphans}")
        print("\nDone. Documents naming a customer and a car will claim any "
              "remaining orphans as they are saved.")


if __name__ == "__main__":
    main()
