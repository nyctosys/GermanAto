"""Workshop KPI aggregates for the ERP dashboard (real data only)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.invoice_math import invoice_amount_remaining
from app.models import (
    GatePass,
    Inventory,
    Invoice,
    InvoiceItem,
    JobCard,
    QcSignoff,
    RepairOrder,
)


OPEN_RO = ("received", "in_progress", "waiting_parts", "complete", "completed", "qc_pending")


def workshop_kpis(db: Session) -> dict:
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    open_ros = (
        db.query(RepairOrder)
        .filter(
            RepairOrder.deleted_at.is_(None),
            RepairOrder.current_status.notin_(("delivered", "cancelled")),
        )
        .all()
    )
    open_count = len(open_ros)
    overdue = sum(
        1
        for r in open_ros
        if r.updated_at and r.updated_at < now - timedelta(days=7)
    )
    open_yesterday = (
        db.query(func.count(RepairOrder.id))
        .filter(
            RepairOrder.deleted_at.is_(None),
            RepairOrder.created_at < day_ago,
            or_(
                RepairOrder.current_status.is_(None),
                RepairOrder.current_status.notin_(("delivered", "cancelled")),
            ),
        )
        .scalar()
        or 0
    )
    open_delta_pct = _pct_change(open_count, int(open_yesterday))

    def _is_unassigned(r: RepairOrder) -> bool:
        if r.worker_id:
            return False
        if (r.worker_name or "").strip():
            return False
        wj = (r.workers_json or "").strip()
        if wj and wj not in ("[]", "null"):
            return False
        return True

    unassigned = sum(1 for r in open_ros if _is_unassigned(r))

    pending_approvals = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.deleted_at.is_(None),
            Invoice.type_of == "quote",
            Invoice.status == "pending",
        )
        .scalar()
        or 0
    )
    # Count quotes that still have pending lines
    quotes = (
        db.query(Invoice)
        .filter(Invoice.deleted_at.is_(None), Invoice.type_of == "quote")
        .limit(500)
        .all()
    )
    pending_line_quotes = 0
    for q in quotes:
        items = list(q.items or [])
        labs = list(q.labours or [])
        if any((i.approval_status or "pending") == "pending" for i in items) or any(
            (l.approval_status or "pending") == "pending" for l in labs
        ):
            pending_line_quotes += 1

    in_repair = sum(1 for r in open_ros if (r.current_status or "") in ("in_progress", "waiting_parts", "received"))
    qc_waiting = 0
    for r in open_ros:
        if (r.current_status or "") in ("complete", "completed", "in_progress"):
            has_qc = (
                db.query(QcSignoff.id)
                .filter(QcSignoff.repair_order_id == r.id, QcSignoff.deleted_at.is_(None))
                .first()
            )
            if not has_qc:
                qc_waiting += 1

    invoices = (
        db.query(Invoice)
        .filter(Invoice.deleted_at.is_(None), Invoice.type_of == "invoice")
        .limit(2000)
        .all()
    )
    receivables = round(sum(max(0.0, invoice_amount_remaining(inv)) for inv in invoices), 2)
    unpaid_count = sum(1 for inv in invoices if invoice_amount_remaining(inv) > 0)

    low_stock_rows = (
        db.query(Inventory)
        .filter(Inventory.deleted_at.is_(None), Inventory.quantity <= Inventory.reorder_level)
        .order_by(Inventory.quantity.asc())
        .limit(20)
        .all()
    )
    low_stock = len(low_stock_rows)

    revenue_month = 0.0
    for inv in invoices:
        if inv.created_at and inv.created_at >= month_start:
            revenue_month += float(inv.paid_amount or 0) + float(inv.advance or 0)

    # Workload by technician name from open ROs
    workload: dict[str, int] = {}
    for r in open_ros:
        name = (r.worker_name or "").strip() or "Unassigned"
        for part in name.split(","):
            key = part.strip() or "Unassigned"
            workload[key] = workload.get(key, 0) + 1
    workload_top = sorted(
        [{"name": k, "count": v} for k, v in workload.items()],
        key=lambda x: -x["count"],
    )[:8]

    open_job_cards = (
        db.query(func.count(JobCard.id))
        .filter(JobCard.deleted_at.is_(None), JobCard.status.in_(("open", "quoted")))
        .scalar()
        or 0
    )

    delivered_today = (
        db.query(func.count(GatePass.id))
        .filter(GatePass.deleted_at.is_(None), GatePass.delivered_at >= day_ago)
        .scalar()
        or 0
    )

    return {
        "open_jobs": open_count,
        "overdue_jobs": overdue,
        "open_jobs_delta_pct": open_delta_pct,
        "unassigned": unassigned,
        "unassigned_pct_of_open": round((unassigned / open_count) * 100, 1) if open_count else 0,
        "pending_approvals": max(int(pending_approvals), pending_line_quotes),
        "in_repair": in_repair,
        "qc_waiting": qc_waiting,
        "receivables": receivables,
        "unpaid_invoices": unpaid_count,
        "low_stock": low_stock,
        "low_stock_items": [
            {"id": i.id, "name": i.name, "quantity": i.quantity, "reorder_level": i.reorder_level}
            for i in low_stock_rows
        ],
        "revenue_month": round(revenue_month, 2),
        "workload": workload_top,
        "open_job_cards": int(open_job_cards),
        "delivered_today": int(delivered_today),
        "generated_at": now.isoformat(),
    }


def _pct_change(current: int, previous: int) -> float:
    if previous <= 0:
        return 0.0 if current == 0 else 100.0
    return round(((current - previous) / previous) * 100, 1)
