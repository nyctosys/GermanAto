# ZKTeco attendance device service (pull method) using pyzk

import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

try:
    from zk import ZK
    PYZK_AVAILABLE = True
except ImportError:
    ZK = None
    PYZK_AVAILABLE = False
    logger.warning("pyzk not installed. Install with: pip install pyzk")


def _normalize_user_id(user_id: Any) -> str:
    """Normalize user_id from device to string for matching Worker.employee_id."""
    if user_id is None:
        return ""
    return str(user_id).strip()


def connect_device(ip_address: str, port: int = 4370, timeout: int = 30):
    """
    Connect to ZKTeco device. Returns (conn, error_message).
    conn has get_attendance(), disconnect(); caller must call disconnect when done.
    """
    if not PYZK_AVAILABLE:
        return None, "pyzk library is not installed. Run: pip install pyzk"
    try:
        zk = ZK(ip_address, port=port, timeout=timeout)
        conn = zk.connect()
        if conn is None or conn is False:
            return None, "Connection failed or returned None"
        return conn, None
    except Exception as e:
        logger.exception("ZKTeco connect failed")
        return None, str(e)


def disconnect_device(conn) -> None:
    """Safely disconnect from device."""
    if conn is None:
        return
    try:
        if hasattr(conn, "disconnect"):
            conn.disconnect()
    except Exception as e:
        logger.warning("Disconnect warning: %s", e)


def get_attendance_logs(
    ip_address: str,
    port: int = 4370,
    timeout: int = 30,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict]:
    """
    Fetch attendance logs from ZKTeco device (pull).
    Each log: user_id (str), timestamp (datetime), punch (0=in, 1=out), status.
    Optional start_date/end_date filter by log date.
    """
    if not PYZK_AVAILABLE:
        return []
    conn, err = connect_device(ip_address, port, timeout)
    if err:
        logger.error("Cannot connect to device: %s", err)
        return []
    out = []
    try:
        logs = conn.get_attendance()
        if not logs:
            return []
        for log in logs:
            try:
                user_id = getattr(log, "user_id", None) or getattr(log, "user_id", "")
                ts = getattr(log, "timestamp", None)
                punch = getattr(log, "punch", 0)
                status = getattr(log, "status", 0)
                if ts is None:
                    continue
                log_date = ts.date() if hasattr(ts, "date") else date(ts.year, ts.month, ts.day)
                if start_date and log_date < start_date:
                    continue
                if end_date and log_date > end_date:
                    continue
                out.append({
                    "user_id": _normalize_user_id(user_id),
                    "timestamp": ts,
                    "punch": punch,
                    "status": status,
                    "date": log_date,
                })
            except Exception as e:
                logger.warning("Skip invalid log entry: %s", e)
                continue
        return out
    except Exception as e:
        logger.exception("get_attendance failed")
        return []
    finally:
        disconnect_device(conn)


def test_connection(ip_address: str, port: int = 4370, timeout: int = 10) -> tuple:
    """Test if device is reachable. Returns (success: bool, message: str)."""
    if not PYZK_AVAILABLE:
        return False, "pyzk not installed"
    conn, err = connect_device(ip_address, port, timeout)
    if err:
        return False, err
    try:
        conn.get_firmware_version()
        return True, "Connected successfully"
    except Exception as e:
        return False, str(e)
    finally:
        disconnect_device(conn)
