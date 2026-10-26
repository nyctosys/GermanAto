"""Additive pipeline columns + legacy visit backfill. Safe to re-run."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.foundation.branch import DEFAULT_BRANCH_ID

PIPELINE_COLUMNS: dict[str, dict[str, str]] = {
    "invoice": {
        "visit_id": "INTEGER NULL",
        "job_card_id": "INTEGER NULL",
        "repair_order_id": "INTEGER NULL",
        "locked_at": "TIMESTAMP NULL",
        "parent_quote_id": "INTEGER NULL",
        "is_variation": "BOOLEAN DEFAULT FALSE",
    },
    "invoice_item": {
        "proposed_price": "DOUBLE PRECISION NULL",
        "inventory_id": "INTEGER NULL",
        "job_card_line_id": "INTEGER NULL",
        "approval_status": "VARCHAR(20) DEFAULT 'pending'",
    },
    "invoice_labour": {
        "proposed_price": "DOUBLE PRECISION NULL",
        "labour_code_id": "INTEGER NULL",
        "std_hours": "DOUBLE PRECISION NULL",
        "job_card_line_id": "INTEGER NULL",
        "approval_status": "VARCHAR(20) DEFAULT 'pending'",
    },
    "inventory": {
        "qty_reserved": "INTEGER DEFAULT 0",
    },
    "repair_order": {
        "visit_id": "INTEGER NULL",
        "job_card_id": "INTEGER NULL",
        "quote_invoice_id": "INTEGER NULL",
        "qc_signoff_id": "INTEGER NULL",
        "payment_gate_bypassed": "BOOLEAN DEFAULT FALSE",
    },
    "repair_order_part": {
        "qty_reserved": "INTEGER DEFAULT 0",
        "qty_issued": "INTEGER DEFAULT 0",
        "qty_returned": "INTEGER DEFAULT 0",
        "from_variation_id": "INTEGER NULL",
    },
    "repair_order_labour": {
        "labour_code_id": "INTEGER NULL",
        "from_variation_id": "INTEGER NULL",
    },
    "purchase_orders": {
        "inventory_id": "INTEGER NULL",
        "qty_received": "INTEGER DEFAULT 0",
        "job_card_id": "INTEGER NULL",
        "quote_invoice_id": "INTEGER NULL",
    },
}


def _existing_columns(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def add_pipeline_columns() -> None:
    for table, cols in PIPELINE_COLUMNS.items():
        existing = _existing_columns(table)
        if not existing:
            continue
        with engine.begin() as conn:
            for name, ddl in cols.items():
                if name in existing:
                    continue
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
                print(f"  + {table}.{name}")


def backfill_legacy_visits(db: Session) -> int:
    """Auto-create a minimal visit for legacy quotes/ROs/invoices with car_id but no visit."""
    from app.models import Invoice, JobCard, RepairOrder, Visit

    created = 0
    docs: list = []
    docs.extend(db.query(Invoice).filter(Invoice.car_id.isnot(None), Invoice.visit_id.is_(None)).all())
    docs.extend(
        db.query(RepairOrder).filter(RepairOrder.car_id.isnot(None), RepairOrder.visit_id.is_(None)).all()
    )

    # Deduplicate by (type, id) — process ROs and invoices separately
    seen_cars: dict[int, int] = {}  # car_id -> visit_id for this run

    for doc in docs:
        car_id = doc.car_id
        if not car_id:
            continue
        if car_id in seen_cars:
            visit_id = seen_cars[car_id]
        else:
            # Prefer an existing visit for this car
            existing = (
                db.query(Visit)
                .filter(Visit.car_id == car_id, Visit.deleted_at.is_(None))
                .order_by(Visit.id.desc())
                .first()
            )
            if existing and existing.signature_attachment_id and existing.items:
                visit_id = existing.id
            else:
                from app.models import Attachment, VisitInspectionItem

                visit = existing or Visit(
                    car_id=car_id,
                    customer_id=getattr(doc, "customer_id", None),
                    status="completed",
                    reported_complaints="Legacy auto check-in (pipeline migration)",
                    checked_in_by="system",
                    check_in_at=getattr(doc, "created_at", None) or datetime.utcnow(),
                    branch_id=getattr(doc, "branch_id", None) or DEFAULT_BRANCH_ID,
                )
                if not existing:
                    db.add(visit)
                    db.flush()
                    created += 1
                if not visit.signature_attachment_id:
                    att = Attachment(
                        branch_id=visit.branch_id or DEFAULT_BRANCH_ID,
                        entity_type="visit_signature",
                        entity_id=visit.id,
                        file_path="uploads/legacy_signature.png",
                        original_name="legacy_signature.png",
                        content_type="image/png",
                        uploaded_by="system",
                        notes="legacy migration placeholder",
                    )
                    db.add(att)
                    db.flush()
                    visit.signature_attachment_id = att.id
                if not visit.items:
                    db.add(
                        VisitInspectionItem(
                            visit_id=visit.id,
                            point_key="legacy",
                            label="Legacy migration",
                            category="general",
                            result="ok",
                            sort_order=0,
                        )
                    )
                visit_id = visit.id
            seen_cars[car_id] = visit_id

        doc.visit_id = visit_id
        if isinstance(doc, RepairOrder) and doc.visit_id:
            visit_obj = db.get(Visit, visit_id)
            if visit_obj and not visit_obj.repair_order_id:
                visit_obj.repair_order_id = doc.id

        # Ensure a job card exists for car docs
        if isinstance(doc, (Invoice, RepairOrder)) and doc.car_id:
            jc = (
                db.query(JobCard)
                .filter(JobCard.car_id == doc.car_id, JobCard.visit_id == visit_id)
                .first()
            )
            if not jc:
                jc = JobCard(
                    visit_id=visit_id,
                    car_id=doc.car_id,
                    customer_id=getattr(doc, "customer_id", None),
                    customer_name=getattr(doc, "customer_name", "") or "",
                    customer_phone=getattr(doc, "customer_phone", "") or "",
                    customer_reg_no=getattr(doc, "customer_reg_no", "") or "",
                    customer_made=getattr(doc, "customer_made", "") or "",
                    status="quoted" if isinstance(doc, Invoice) else "open",
                    notes="Legacy auto job card",
                    created_by_user="system",
                    branch_id=getattr(doc, "branch_id", None) or DEFAULT_BRANCH_ID,
                )
                if isinstance(doc, Invoice) and (doc.type_of or "").lower() == "quote":
                    jc.quote_invoice_id = doc.id
                db.add(jc)
                db.flush()
            if getattr(doc, "job_card_id", None) is None:
                doc.job_card_id = jc.id
            if isinstance(doc, Invoice) and (doc.type_of or "").lower() == "quote":
                jc.quote_invoice_id = jc.quote_invoice_id or doc.id
            if isinstance(doc, RepairOrder):
                doc.job_card_id = doc.job_card_id or jc.id

    return created


def run() -> int:
    print("Adding pipeline columns...")
    add_pipeline_columns()
    print("Backfilling legacy visits/job cards...")
    db = SessionLocal()
    try:
        n = backfill_legacy_visits(db)
        db.commit()
        print(f"  created {n} legacy visits")
    except Exception as exc:
        db.rollback()
        print(f"  (skip legacy backfill: {exc})")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    run()
