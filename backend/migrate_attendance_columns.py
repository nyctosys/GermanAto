"""
Add new columns to attendance_records table.
Run once from backend: python migrate_attendance_columns.py

Adds (if missing):
  - source: VARCHAR(50) NULL — e.g. 'manual', 'ZKTeco push'
  - zkteco_device_id: INT NULL, FK to zkteco_devices(id) — device that sent the record

Edit NEW_COLUMNS below to add more columns; each is (name, sql_type, after_column).
"""
import os
import sys
from urllib.parse import urlparse, unquote

from dotenv import load_dotenv
load_dotenv()

DEFAULT_USER = "germanato_user"
DEFAULT_PASSWORD = "germanato_password_2024"
DEFAULT_DB = "germanato_db"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3306

TABLE = "attendance_records"

# (column_name, full SQL type + null/default, column to add AFTER; None = end)
NEW_COLUMNS = [
    ("source", "VARCHAR(50) NULL", "notes"),
    ("zkteco_device_id", "INT NULL", "source"),
]


def get_connection():
    try:
        import pymysql
    except ImportError:
        print("PyMySQL required. Install with: pip install PyMySQL")
        sys.exit(1)

    host = DEFAULT_HOST
    port = DEFAULT_PORT
    user = DEFAULT_USER
    password = DEFAULT_PASSWORD
    db = DEFAULT_DB

    url = os.getenv("DATABASE_URL")
    if url and url.strip().lower().startswith("mysql"):
        parsed = urlparse(url)
        if parsed.hostname is not None:
            host = parsed.hostname
        if parsed.port is not None:
            port = parsed.port
        if parsed.username is not None:
            user = unquote(parsed.username)
        if parsed.password is not None:
            password = unquote(parsed.password)
        if (parsed.path or "").strip("/"):
            db = (parsed.path or "").strip("/")

    return pymysql.connect(host=host, port=port, user=user, password=password, database=db)


def column_exists(cursor, table, column):
    cursor.execute("SHOW COLUMNS FROM {} WHERE Field = %s".format(table), (column,))
    return cursor.fetchone() is not None


def main():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
            (TABLE,),
        )
        if cur.fetchone() is None:
            print("Table {} does not exist. Create it first (e.g. run the app to create tables).".format(TABLE))
            sys.exit(1)

        for name, sql_type, after in NEW_COLUMNS:
            if column_exists(cur, TABLE, name):
                print("Column {} already exists, skip.".format(name))
                continue
            after_clause = "AFTER {}".format(after) if after else ""
            sql = "ALTER TABLE {} ADD COLUMN {} {} {}".format(TABLE, name, sql_type, after_clause).strip()
            cur.execute(sql)
            print("Added column {}.".format(name))

        # Optional: add FK for zkteco_device_id if we added it
        if "zkteco_device_id" in [c[0] for c in NEW_COLUMNS]:
            if column_exists(cur, TABLE, "zkteco_device_id"):
                cur.execute(
                    "SELECT 1 FROM information_schema.TABLE_CONSTRAINTS "
                    "WHERE table_schema = DATABASE() AND table_name = %s AND constraint_name = 'fk_attendance_zkteco_device'",
                    (TABLE,),
                )
                if cur.fetchone() is None:
                    try:
                        cur.execute(
                            "ALTER TABLE {} ADD CONSTRAINT fk_attendance_zkteco_device "
                            "FOREIGN KEY (zkteco_device_id) REFERENCES zkteco_devices(id)".format(TABLE)
                        )
                        print("Added FK fk_attendance_zkteco_device.")
                    except Exception as e:
                        print("Note: Could not add FK (e.g. zkteco_devices missing or existing data):", e)

        conn.commit()
        print("Migration done.")
    except Exception as e:
        conn.rollback()
        print("Error:", e)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
