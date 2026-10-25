"""Reusable evidence / attachment storage on top of log_utils uploads."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.log_utils import save_uploaded_file


def save_evidence(
    db: Session,
    file,
    *,
    entity_type: str,
    entity_id: int | None = None,
    branch_id: str | None = None,
    uploaded_by: str | None = None,
    notes: str | None = None,
) -> Optional[dict]:
    """
    Save an uploaded file and register an Attachment row.
    Returns a dict suitable for API responses, or None if no file.
    """
    from app.foundation.branch import DEFAULT_BRANCH_ID
    from app.models import Attachment

    path = save_uploaded_file(file)
    if not path:
        return None

    filename = getattr(file, "filename", None) or path.rsplit("/", 1)[-1]
    content_type = getattr(file, "content_type", None)

    row = Attachment(
        branch_id=branch_id or DEFAULT_BRANCH_ID,
        entity_type=entity_type,
        entity_id=entity_id,
        file_path=path,
        original_name=filename,
        content_type=content_type,
        uploaded_by=uploaded_by,
        notes=notes,
    )
    db.add(row)
    db.flush()
    return {
        "id": row.id,
        "file_path": row.file_path,
        "original_name": row.original_name,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "branch_id": row.branch_id,
    }
