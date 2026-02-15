"""
One-off migration: add serial_number to zkteco_devices and make ip_address/port nullable.
Run once: python migrate_zkteco_adms.py
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

def main():
    try:
        import pymysql
    except ImportError:
        print("PyMySQL required. Install with: pip install PyMySQL")
        sys.exit(1)
    url = os.getenv("DATABASE_URL")
    if not url or not url.startswith("mysql"):
        print("Set DATABASE_URL (MySQL) in .env")
        sys.exit(1)
    # Parse simple mysql://user:pass@host/db
    from urllib.parse import urlparse, unquote
    parsed = urlparse(url)
    if parsed.scheme != "mysql":
        print("DATABASE_URL must be mysql://...")
        sys.exit(1)
    host = parsed.hostname or "localhost"
    port = parsed.port or 3306
    user = unquote(parsed.username) if parsed.username else "root"
    password = unquote(parsed.password) if parsed.password else ""
    db = (parsed.path or "").strip("/") or "germanato"
    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=db)
    cur = conn.cursor()
    try:
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
        conn.commit()
        print("Migration done.")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
