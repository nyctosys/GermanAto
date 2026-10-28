import os
import re
from pathlib import Path


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:5432/germanato")
    # Hosts hand out postgres:// URLs; SQLAlchemy would pick psycopg2 for those.
    return re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)


DATABASE_URL = _database_url()
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", Path(__file__).resolve().parent.parent / "storage"))
# Secure cookies need HTTPS; the branch server on the LAN runs plain HTTP.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "14"))
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Attendance devices send local wall-clock times; this is the workshop's zone.
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Karachi")
