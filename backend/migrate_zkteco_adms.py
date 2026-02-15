"""
One-off migration: add serial_number to zkteco_devices and make ip_address/port nullable.
Run once: python migrate_zkteco_adms.py
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Default connection (used when DATABASE_URL is not set or not parseable)
DEFAULT_USER = "germanato_user"
DEFAULT_PASSWORD = "germanato_password_2024"
DEFAULT_DB = "germanato_db"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3306


def main():
    try:
        import pymysql
    except ImportError:
        print("PyMySQL required. Install with: pip install PyMySQL")
        sys.exit(1)
    from urllib.parse import urlparse, unquote

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

    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=db)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = 'zkteco_devices'",
            (db,)
        )
        table_exists = cur.fetchone() is not None

        if not table_exists:
            cur.execute("""
                CREATE TABLE zkteco_devices (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    serial_number VARCHAR(64) UNIQUE NULL,
                    ip_address VARCHAR(45) NULL,
                    port INT NULL,
                    timeout INT NOT NULL DEFAULT 30,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    last_sync DATETIME NULL,
                    last_sync_status VARCHAR(50) NULL,
                    last_seen_at DATETIME NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL
                )
            """)
            print("Created table zkteco_devices")
        else:
            cur.execute("SHOW COLUMNS FROM zkteco_devices LIKE 'serial_number'")
            if cur.fetchone() is None:
                cur.execute("ALTER TABLE zkteco_devices ADD COLUMN serial_number VARCHAR(64) UNIQUE NULL AFTER name")
                print("Added column serial_number")
            else:
                print("Column serial_number already exists")
            cur.execute("SHOW COLUMNS FROM zkteco_devices WHERE Field = 'ip_address'")
            row = cur.fetchone()
            if row and "YES" not in str(row[2]).upper():
                cur.execute("ALTER TABLE zkteco_devices MODIFY COLUMN ip_address VARCHAR(45) NULL")
                print("Made ip_address nullable")
            cur.execute("SHOW COLUMNS FROM zkteco_devices WHERE Field = 'port'")
            row = cur.fetchone()
            if row and "YES" not in str(row[2]).upper():
                cur.execute("ALTER TABLE zkteco_devices MODIFY COLUMN port INT NULL")
                print("Made port nullable")
            cur.execute("SHOW COLUMNS FROM zkteco_devices LIKE 'last_seen_at'")
            if cur.fetchone() is None:
                cur.execute("ALTER TABLE zkteco_devices ADD COLUMN last_seen_at DATETIME NULL AFTER last_sync_status")
                print("Added column last_seen_at")
        conn.commit()
        print("Migration done.")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
