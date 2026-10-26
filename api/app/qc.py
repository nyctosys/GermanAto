"""QC sign-off gate before invoice issue."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.foundation.audit import audit_write
from app.foundation.overrides import require_override
from app.models import QcSignoff, RepairOrder


def create_qc_signoff(db: Session, ro: RepairOrder, data: dict, user) -> QcSignoff:
    require_override(db, user, "qc_signoff", reason=data.get("reason") or "QC sign-off")
    checklist = data.get("checklist") or []
    if not isinstance(checklist, list) or not checklist:
        raise HTTPException(status_code=400, detail="QC checklist is required")
    photos = data.get("photos") or []
    row = QcSignoff(
        repair_order_id=ro.id,
        checklist_json=json.dumps(checklist),
        road_test_note=data.get("road_test_note"),
        photos_json=json.dumps(photos if isinstance(photos, list) else []),
        signed_by=getattr(user, "username", None),
        signed_at=datetime.utcnow(),
        branch_id=ro.branch_id,
    )
    db.add(row)
    db.flush()
    ro.qc_signoff_id = row.id
    # Mark labour lines QC passed where Done
    for lab in ro.labour or []:
        if (lab.status or "").lower() in ("done", "complete", "completed"):
            lab.status = "QC passed"
    audit_write(
        db,
        user=user,
        action="QC_SIGNOFF",
        module="repair_orders",
        reference_id=ro.id,
        details="Foreman QC sign-off",
        new_value=row.to_dict(),
        reason=data.get("reason") or "QC sign-off",
    )
    return row
