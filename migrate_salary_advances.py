"""Create the salary_advances table.

Partial salary drawn during the month. Deliberately not an Expense: the full
month's salary is the expense when payroll runs, so recording the advance there
too would book the same rupee twice. calculate_salary() nets these off instead.

    DATABASE_URL="mysql+pymysql://user:pass@localhost/germanato_db" \\
        python3 migrate_salary_advances.py [--apply]
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
CREATE TABLE salary_advances (
    id INT AUTO_INCREMENT PRIMARY KEY,
    worker_id INT NOT NULL,
    date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    payment_method VARCHAR(50) NULL,
    notes TEXT NULL,
    created_by VARCHAR(100) NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    INDEX idx_salary_advances_worker (worker_id),
    INDEX idx_salary_advances_date (date),
    -- One worker, one month: the cap in the API is only meaningful if a
    -- deleted worker takes their advances with them.
    CONSTRAINT fk_salary_advances_worker FOREIGN KEY (worker_id)
        REFERENCES workers(id) ON DELETE CASCADE,
    CONSTRAINT chk_salary_advance_positive CHECK (amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def table_exists(conn, name):
    return conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = :t"), {"t": name}).scalar() > 0


def main():
    with app.app_context():
        with db.engine.begin() as conn:
            if table_exists(conn, "salary_advances"):
                rows = conn.execute(text("SELECT COUNT(*) FROM salary_advances")).scalar()
                print(f"  = salary_advances already exists ({rows} rows)")
            elif APPLY:
                if not table_exists(conn, "workers"):
                    sys.exit("  ! workers table is missing - run migrate_release_schema.py first")
                conn.execute(text(CREATE))
                print("  + salary_advances created")
            else:
                print("  ~ salary_advances would be created")

            workers = conn.execute(text(
                "SELECT COUNT(*) FROM workers WHERE salary IS NOT NULL AND salary > 0")).scalar()
            print(f"\n  {workers} workers have a monthly salary set and can take advances")

        if not APPLY:
            print("\nDry run - nothing written. Re-run with --apply to commit.")


if __name__ == "__main__":
    main()
