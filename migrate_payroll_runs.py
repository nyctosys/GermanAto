"""Create the payroll_runs table.

Running payroll books each worker's earned salary as an expense. This table is
what makes that idempotent: without it, running September twice would book
September's wages twice and nothing downstream would notice.

It doubles as the payroll history - which month was paid, when, by whom, and
which expense row it produced.

    DATABASE_URL="mysql+pymysql://user:pass@localhost/germanato_db" \\
        python3 migrate_payroll_runs.py [--apply]
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

CREATE = """
CREATE TABLE payroll_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    worker_id INT NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    earned_salary DECIMAL(10,2) NOT NULL,
    advances_total DECIMAL(10,2) NOT NULL DEFAULT 0,
    net_paid DECIMAL(10,2) NOT NULL,
    expense_id INT NULL,
    run_by VARCHAR(100) NULL,
    run_at DATETIME NULL,
    INDEX idx_payroll_runs_worker (worker_id),
    -- The guard: one worker cannot be paid twice for the same month.
    CONSTRAINT uq_payroll_worker_month UNIQUE (worker_id, year, month),
    CONSTRAINT fk_payroll_runs_worker FOREIGN KEY (worker_id)
        REFERENCES workers(id) ON DELETE CASCADE,
    -- SET NULL: deleting the expense row must not erase the fact of payment.
    CONSTRAINT fk_payroll_runs_expense FOREIGN KEY (expense_id)
        REFERENCES expense(id) ON DELETE SET NULL,
    CONSTRAINT chk_payroll_month CHECK (month BETWEEN 1 AND 12)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def table_exists(conn, name):
    return conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = :t"), {"t": name}).scalar() > 0


def main():
    with app.app_context():
        with db.engine.begin() as conn:
            if table_exists(conn, "payroll_runs"):
                rows = conn.execute(text("SELECT COUNT(*) FROM payroll_runs")).scalar()
                print(f"  = payroll_runs already exists ({rows} rows)")
            elif APPLY:
                for required in ("workers", "expense"):
                    if not table_exists(conn, required):
                        sys.exit(f"  ! {required} table is missing - run the earlier migrations first")
                conn.execute(text(CREATE))
                print("  + payroll_runs created")
            else:
                print("  ~ payroll_runs would be created")

            workers = conn.execute(text(
                "SELECT COUNT(*) FROM workers WHERE status = 'active' "
                "AND salary IS NOT NULL AND salary > 0")).scalar()
            legacy = conn.execute(text(
                "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM expense "
                "WHERE category = 'Labor'")).first()

        print(f"\n  {workers} active workers have a salary set")
        print(f"  {legacy[0]} hand-keyed Labor expenses already exist, "
              f"totalling {float(legacy[1]):,.2f}")
        print("  Those stay exactly as they are - payroll only books months you "
              "run from now on,\n  so nothing is double-counted.")

        if not APPLY:
            print("\nDry run - nothing written. Re-run with --apply to commit.")


if __name__ == "__main__":
    main()
