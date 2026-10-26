"""Permanent human-readable document / entity codes.

Integer PKs stay the system of record. Codes are assigned once after insert
(when the id is known) and never recycled. Existing rows are backfilled by
migration using the same format.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session


def customer_code(entity_id: int) -> str:
    return f"CN{int(entity_id):03d}"


def car_code(entity_id: int) -> str:
    return f"VH{int(entity_id):03d}"


def invoice_document_no(entity_id: int, *, type_of: str | None = None) -> str:
    prefix = "QT" if (type_of or "").lower() in ("quote", "quotation", "estimate") else "INV"
    return f"{prefix}-{int(entity_id):05d}"


def repair_order_document_no(entity_id: int) -> str:
    return f"RO-{int(entity_id):05d}"


def job_card_document_no(entity_id: int) -> str:
    return f"JC-{int(entity_id):05d}"


def expense_document_no(entity_id: int) -> str:
    return f"EXP-{int(entity_id):05d}"


def cash_document_no(entity_id: int) -> str:
    return f"CR-{int(entity_id):05d}"


def po_document_no(entity_id: int) -> str:
    return f"PO-{int(entity_id):05d}"


def gate_pass_document_no(entity_id: int) -> str:
    return f"GP-{int(entity_id):05d}"


def worker_display_code(employee_id: str | None, entity_id: int) -> str:
    if employee_id:
        return str(employee_id)
    return f"EMP-{int(entity_id):03d}"


def vendor_code(entity_id: int) -> str:
    return f"VN{int(entity_id):03d}"


def assign_document_numbers(session: Session) -> int:
    """Fill empty code/document_no after PK assignment. Returns count updated."""
    from app.models import (
        Car,
        CashReceived,
        Customer,
        Expense,
        YardGatePass,
        Invoice,
        JobCard,
        PurchaseOrder,
        RepairOrder,
        Vendor,
    )

    updated = 0
    # After flush, new rows leave session.new; use identity map + pending.
    candidates = set(list(session.new) + list(session.dirty))
    try:
        candidates.update(session.identity_map.values())
    except Exception:
        pass
    for obj in candidates:
        if getattr(obj, "id", None) is None:
            continue
        if isinstance(obj, Customer) and not getattr(obj, "code", None):
            obj.code = customer_code(obj.id)
            updated += 1
        elif isinstance(obj, Car) and not getattr(obj, "code", None):
            obj.code = car_code(obj.id)
            updated += 1
        elif isinstance(obj, Vendor) and not getattr(obj, "code", None):
            obj.code = vendor_code(obj.id)
            updated += 1
        elif isinstance(obj, Invoice) and not getattr(obj, "document_no", None):
            obj.document_no = invoice_document_no(obj.id, type_of=getattr(obj, "type_of", None))
            updated += 1
        elif isinstance(obj, RepairOrder) and not getattr(obj, "document_no", None):
            obj.document_no = repair_order_document_no(obj.id)
            updated += 1
        elif isinstance(obj, JobCard) and not getattr(obj, "document_no", None):
            obj.document_no = job_card_document_no(obj.id)
            updated += 1
        elif isinstance(obj, Expense) and not getattr(obj, "document_no", None):
            obj.document_no = expense_document_no(obj.id)
            updated += 1
        elif isinstance(obj, CashReceived) and not getattr(obj, "document_no", None):
            obj.document_no = cash_document_no(obj.id)
            updated += 1
        elif isinstance(obj, PurchaseOrder) and not getattr(obj, "document_no", None):
            obj.document_no = po_document_no(obj.id)
            updated += 1
        elif isinstance(obj, YardGatePass) and not getattr(obj, "document_no", None):
            obj.document_no = gate_pass_document_no(obj.id)
            updated += 1
    return updated


def stamp_actors(session: Session) -> None:
    """Set created_by_user / updated_by_user when columns exist."""
    from app.foundation.context import get_user

    user = get_user()
    username = getattr(user, "username", None) if user else None
    if not username:
        return
    now = datetime.utcnow()
    for obj in list(session.new):
        if hasattr(obj, "created_by_user") and not getattr(obj, "created_by_user", None):
            obj.created_by_user = username
        if hasattr(obj, "updated_by_user"):
            obj.updated_by_user = username
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            obj.updated_at = now
    for obj in list(session.dirty):
        if hasattr(obj, "updated_by_user"):
            obj.updated_by_user = username
