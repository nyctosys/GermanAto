"""Upload helpers and application audit log."""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")


def secure_filename(filename: str) -> str:
    """Basename-only filename with unsafe characters stripped."""
    name = os.path.basename(filename.replace("\\", "/")).strip()
    keep = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", "."):
            keep.append(ch)
        elif ch.isspace():
            keep.append("_")
    cleaned = "".join(keep).strip("._")
    return cleaned or "file"


def save_uploaded_file(file) -> Optional[str]:
    """Save an uploaded file securely with a unique timestamp prefix."""
    filename = getattr(file, "filename", None) or ""
    if not file or filename == "":
        return None
    try:
        sec_filename = secure_filename(filename)
        unique_name = f"{int(time.time())}_{sec_filename}"
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file_path = os.path.join(UPLOAD_FOLDER, unique_name)
        if hasattr(file, "save"):
            file.save(file_path)
        else:
            with open(file_path, "wb") as out:
                content = file.file.read()
                out.write(content)
        return f"uploads/{unique_name}"
    except Exception as e:
        logger.error(f"Error saving uploaded file: {e}")
        return None


def log_action(db: Session, user, action, module, reference_id, details, request: Request | None = None):
    """Log an application action to the database."""
    try:
        from app.models import AppLog

        ip_address = None
        if request is not None:
            ip_address = request.headers.get("X-Forwarded-For") or (
                request.client.host if request.client else None
            )
            if ip_address and "," in ip_address:
                ip_address = ip_address.split(",")[0].strip()

        user_id = user.id if user else None
        username = user.username if user else "anonymous/system"

        log_entry = AppLog(
            user_id=user_id,
            username=username,
            action=action,
            module=module,
            reference_id=reference_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(log_entry)
        db.flush()
        logger.info(f"AppLog: [{username}] {action} in {module} ({reference_id}): {details}")
    except Exception as e:
        logger.error(f"Failed to write app log: {e}")


DOCUMENT_LOG_MODULES = {
    "invoice": ("invoice", "invoices", "quote", "quotes"),
    "repair-order": ("repair_order", "repair_orders"),
}


def document_log_entries(db: Session, kind, reference_id):
    """Everything recorded against one document, oldest first."""
    from app.models import AppLog

    modules = DOCUMENT_LOG_MODULES.get(kind)
    if not modules:
        return []

    rows = (
        db.query(AppLog)
        .filter(
            AppLog.module.in_(modules),
            AppLog.reference_id == reference_id,
        )
        .order_by(AppLog.created_at.asc(), AppLog.id.asc())
        .all()
    )

    return [
        {
            "when": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            "action": r.action,
            "details": r.details,
            "user": r.username or "system",
            "ip_address": r.ip_address or "",
        }
        for r in rows
    ]
