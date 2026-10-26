"""Gate pass / handover after payment gate; starts comeback window via delivered_at."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.foundation.audit import audit_write
from app.log_utils import save_data_url
from app.models import Attachment, GatePass, Invoice, RepairOrder
from app.parts_flow import return_unused_on_close
from app.pipeline import (
    assert_no_duplicate_gate_pass,
    assert_payment_gate_for_delivery,
    mark_ro_delivered,
)
from app.whatsapp_notifications import whatsapp_notifier


def create_gate_pass(db: Session, ro: RepairOrder, data: dict, user) -> GatePass:
    assert_no_duplicate_gate_pass(db, ro.id)
    invoice_id = data.get("invoice_id") or None
    invoice = db.get(Invoice, int(invoice_id)) if invoice_id else None
    if invoice is None and ro.quote_invoice_id:
        # Prefer issued invoice linked to this RO
        invoice = (
            db.query(Invoice)
            .filter(
                Invoice.repair_order_id == ro.id,
                Invoice.type_of == "invoice",
                Invoice.deleted_at.is_(None),
            )
            .order_by(Invoice.id.desc())
            .first()
        )

    bypass = bool(data.get("payment_gate_bypass") or data.get("bypass"))
    reason = assert_payment_gate_for_delivery(
        db,
        user,
        invoice,
        bypass=bypass,
        reason=data.get("reason"),
        branch_id=ro.branch_id,
    )

    checklist = data.get("old_parts_checklist") or []
    if not isinstance(checklist, list):
        raise HTTPException(status_code=400, detail="old_parts_checklist must be a list")
    photos = data.get("photos") or []
    sig_path = save_data_url(data.get("signature_data_url"), prefix="gatepass_sig")
    sig_att = None
    if sig_path:
        sig_att = Attachment(
            branch_id=ro.branch_id or "a1b2c3d4",
            entity_type="gate_pass",
            entity_id=None,
            file_path=sig_path,
            original_name="signature.png",
            content_type="image/png",
            uploaded_by=getattr(user, "username", None),
            notes="gate pass signature",
        )
        db.add(sig_att)
        db.flush()

    row = GatePass(
        repair_order_id=ro.id,
        invoice_id=invoice.id if invoice else None,
        visit_id=ro.visit_id,
        old_parts_checklist_json=json.dumps(checklist),
        exit_odometer=data.get("exit_odometer"),
        photos_json=json.dumps(photos if isinstance(photos, list) else []),
        signature_attachment_id=sig_att.id if sig_att else None,
        delivered_at=datetime.utcnow(),
        payment_gate_override=bool(bypass and reason),
        override_reason=reason,
        created_by_user=getattr(user, "username", None),
        branch_id=ro.branch_id,
    )
    db.add(row)
    db.flush()
    if sig_att:
        sig_att.entity_id = row.id

    return_unused_on_close(db, ro, created_by=getattr(user, "id", None))
    mark_ro_delivered(ro)
    if bypass and reason:
        ro.payment_gate_bypassed = True

    audit_write(
        db,
        user=user,
        action="GATE_PASS",
        module="repair_orders",
        reference_id=ro.id,
        details="Handover / gate pass",
        new_value=row.to_dict(),
        reason=reason or "delivered",
    )

    try:
        whatsapp_notifier.send_invoice_notification(
            {
                "id": invoice.id if invoice else ro.id,
                "customer_name": ro.customer_name,
                "customer_phone": ro.customer_phone,
                "net_total": float(invoice.net_total) if invoice else 0,
                "type_of": "handover",
            }
        )
    except Exception:
        pass

    return row
