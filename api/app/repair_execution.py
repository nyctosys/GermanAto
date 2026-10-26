"""Repair Execution — technician workbench between RO open and QC.

Labour cost uses LabourCode.rate × actual repair hours.
Payroll hours stay on AttendanceRecord / ZKTeco — never mixed here.
"""

from __future__ import annotations

import json
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.foundation.audit import audit_write
from app.foundation.soft_delete import soft_delete
from app.models import (
    ApprovalToken,
    Attachment,
    Inventory,
    LabourCode,
    RepairFault,
    RepairOrder,
    RepairOrderLabour,
    RepairOrderPart,
    RepairTimeEntry,
    Variation,
    VariationLine,
    Worker,
)
from app.pipeline import next_action
from app.stock import StockError, issue_to_ro, return_from_ro
from app.variations import assert_line_workable, create_variation


_DONE = frozenset({"done", "complete", "completed", "qc passed"})


def _now() -> datetime:
    return datetime.utcnow()


def _rate_for(db: Session, lab: RepairOrderLabour) -> float:
    if lab.labour_rate is not None:
        return float(lab.labour_rate)
    if lab.labour_code_id:
        code = db.get(LabourCode, lab.labour_code_id)
        if code:
            return float(code.rate or 0)
    return 0.0


def _recalc_labour_cost(db: Session, lab: RepairOrderLabour) -> None:
    rate = _rate_for(db, lab)
    lab.labour_rate = rate
    hours = float(lab.actual_hours or 0)
    lab.labour_cost = round(hours * rate, 2)


def _recalc_ro_costs(db: Session, ro: RepairOrder) -> None:
    labour_total = 0.0
    for lab in ro.labour or []:
        _recalc_labour_cost(db, lab)
        labour_total += float(lab.labour_cost or 0)
    parts_total = 0.0
    for part in ro.parts or []:
        consumed = max(0, int(part.qty_issued or 0) - int(part.qty_returned or 0))
        unit = float(part.unit_cost or 0)
        if unit <= 0 and part.inventory_id:
            inv = db.get(Inventory, part.inventory_id)
            if inv and inv.avg_cost is not None:
                unit = float(inv.avg_cost)
                part.unit_cost = unit
        parts_total += consumed * unit
    ro.labour_cost_total = round(labour_total, 2)
    ro.parts_cost_total = round(parts_total, 2)


def _open_time_entry(db: Session, labour_id: int) -> RepairTimeEntry | None:
    return (
        db.query(RepairTimeEntry)
        .filter(
            RepairTimeEntry.labour_id == labour_id,
            RepairTimeEntry.status == "open",
            RepairTimeEntry.deleted_at.is_(None),
        )
        .first()
    )


def _close_entry(entry: RepairTimeEntry, *, at: datetime | None = None) -> float:
    end = at or _now()
    entry.ended_at = end
    entry.status = "closed"
    start = entry.started_at or end
    seconds = max(0.0, (end - start).total_seconds())
    hours = round(seconds / 3600.0, 4)
    entry.hours = hours
    return hours


def _assert_ro_open(ro: RepairOrder) -> None:
    st = (ro.current_status or "").lower()
    if st in ("delivered", "cancelled", "canceled"):
        raise HTTPException(status_code=400, detail="Repair order is closed")


def _assert_labour_workable(db: Session, lab: RepairOrderLabour) -> None:
    approval = (lab.approval_status or "approved").lower()
    assert_line_workable(
        db,
        from_variation_id=lab.from_variation_id,
        approval_status=approval,
    )
    if lab.from_variation_id and approval != "approved":
        raise HTTPException(
            status_code=400,
            detail="Additional work requires customer approval before execution",
        )
    st = (lab.status or "").lower()
    if st in _DONE:
        raise HTTPException(status_code=400, detail="Labour task already completed")


def _assert_part_workable(db: Session, part: RepairOrderPart) -> None:
    approval = (part.approval_status or "approved").lower()
    assert_line_workable(
        db,
        from_variation_id=part.from_variation_id,
        approval_status=approval,
    )
    if part.from_variation_id and approval != "approved":
        raise HTTPException(
            status_code=400,
            detail="Unapproved variation parts cannot be issued",
        )


def get_ro(db: Session, ro_id: int) -> RepairOrder:
    ro = db.get(RepairOrder, ro_id)
    if not ro or getattr(ro, "deleted_at", None):
        raise HTTPException(status_code=404, detail="Repair order not found")
    return ro


def get_labour(db: Session, ro: RepairOrder, labour_id: int) -> RepairOrderLabour:
    lab = db.get(RepairOrderLabour, labour_id)
    if not lab or lab.repair_order_id != ro.id:
        raise HTTPException(status_code=404, detail="Labour task not found")
    return lab


def get_part(db: Session, ro: RepairOrder, part_id: int) -> RepairOrderPart:
    part = db.get(RepairOrderPart, part_id)
    if not part or part.repair_order_id != ro.id:
        raise HTTPException(status_code=404, detail="Part line not found")
    return part


def _progress(ro: RepairOrder) -> dict:
    labs = list(ro.labour or [])
    parts = list(ro.parts or [])
    done_l = sum(1 for l in labs if (l.status or "").lower() in _DONE)
    issued_p = sum(1 for p in parts if int(p.qty_issued or 0) > 0)
    return {
        "labour_total": len(labs),
        "labour_done": done_l,
        "parts_total": len(parts),
        "parts_issued": issued_p,
        "pct": round((done_l / len(labs) * 100) if labs else 0, 1),
    }


def _labour_dict(db: Session, lab: RepairOrderLabour) -> dict:
    code = db.get(LabourCode, lab.labour_code_id) if lab.labour_code_id else None
    open_entry = _open_time_entry(db, lab.id)
    worker_name = None
    if lab.assigned_worker_id:
        w = db.get(Worker, lab.assigned_worker_id)
        if w:
            worker_name = f"{w.first_name or ''} {w.last_name or ''}".strip()
    return {
        "id": lab.id,
        "description": lab.description,
        "status": lab.status,
        "approval_status": lab.approval_status or "approved",
        "labour_code_id": lab.labour_code_id,
        "labour_code": code.code if code else None,
        "labour_code_description": code.description if code else None,
        "from_variation_id": lab.from_variation_id,
        "assigned_worker_id": lab.assigned_worker_id,
        "assigned_worker_name": worker_name,
        "std_hours": lab.std_hours if lab.std_hours is not None else (code.standard_hours if code else None),
        "actual_hours": float(lab.actual_hours or 0),
        "labour_rate": _rate_for(db, lab),
        "labour_cost": float(lab.labour_cost or 0),
        "started_at": lab.started_at.strftime("%Y-%m-%d %H:%M:%S") if lab.started_at else None,
        "paused_at": lab.paused_at.strftime("%Y-%m-%d %H:%M:%S") if lab.paused_at else None,
        "completed_at": lab.completed_at.strftime("%Y-%m-%d %H:%M:%S") if lab.completed_at else None,
        "deadline_at": lab.deadline_at.strftime("%Y-%m-%d %H:%M:%S") if lab.deadline_at else None,
        "line_notes": lab.line_notes,
        "clock_running": open_entry is not None,
        "open_time_entry_id": open_entry.id if open_entry else None,
        "open_clock_started_at": (
            open_entry.started_at.strftime("%Y-%m-%d %H:%M:%S")
            if open_entry and open_entry.started_at
            else None
        ),
        "workable": (lab.approval_status or "approved").lower() == "approved"
        or lab.from_variation_id is None,
        "is_done": (lab.status or "").lower() in _DONE,
    }


def _part_dict(db: Session, part: RepairOrderPart) -> dict:
    inv = db.get(Inventory, part.inventory_id) if part.inventory_id else None
    issued = int(part.qty_issued or 0)
    returned = int(part.qty_returned or 0)
    qty = int(part.quantity or 0)
    return {
        "id": part.id,
        "description": part.description,
        "part_number": part.part_number,
        "inventory_id": part.inventory_id,
        "inventory_name": inv.name if inv else None,
        "quantity": qty,
        "qty_reserved": int(part.qty_reserved or 0),
        "qty_issued": issued,
        "qty_returned": returned,
        "qty_remaining_to_issue": max(0, qty - issued),
        "qty_returnable": max(0, issued - returned),
        "status": part.status,
        "approval_status": part.approval_status or "approved",
        "from_variation_id": part.from_variation_id,
        "ownership_type": part.ownership_type or "shop_stock",
        "unit_cost": float(part.unit_cost or (inv.avg_cost if inv and inv.avg_cost is not None else 0) or 0),
        "old_parts_returned": bool(part.old_parts_returned),
    }


def list_assigned_jobs(db: Session, *, worker_id: int | None = None) -> list[dict]:
    """Technician board: open ROs assigned to a worker (or all open if no filter)."""
    q = db.query(RepairOrder).filter(
        RepairOrder.deleted_at.is_(None),
        RepairOrder.current_status.notin_(["delivered", "cancelled", "canceled"]),
    )
    rows = q.order_by(RepairOrder.id.desc()).limit(100).all()
    out = []
    for ro in rows:
        if worker_id:
            assigned = False
            if ro.worker_id == worker_id:
                assigned = True
            else:
                try:
                    workers = json.loads(ro.workers_json or "[]")
                except Exception:
                    workers = []
                if any(int(w.get("id") or 0) == worker_id for w in workers if isinstance(w, dict)):
                    assigned = True
                if not assigned:
                    for lab in ro.labour or []:
                        if lab.assigned_worker_id == worker_id:
                            assigned = True
                            break
            if not assigned:
                continue
        prog = _progress(ro)
        out.append(
            {
                "id": ro.id,
                "document_no": ro.document_no,
                "customer_name": ro.customer_name,
                "customer_phone": ro.customer_phone,
                "customer_reg_no": ro.customer_reg_no,
                "customer_made": ro.customer_made,
                "customer_mileage": ro.customer_mileage,
                "current_status": ro.current_status,
                "worker_name": ro.worker_name,
                "worker_id": ro.worker_id,
                "due_at": ro.due_at.strftime("%Y-%m-%d %H:%M:%S") if ro.due_at else None,
                "submitted_for_qc_at": (
                    ro.submitted_for_qc_at.strftime("%Y-%m-%d %H:%M:%S")
                    if ro.submitted_for_qc_at
                    else None
                ),
                "labour_cost_total": float(ro.labour_cost_total or 0),
                "parts_cost_total": float(ro.parts_cost_total or 0),
                "job_cost_total": float(ro.labour_cost_total or 0) + float(ro.parts_cost_total or 0),
                "progress": prog,
                "problem_description": ro.problem_description,
                "created_at": ro.created_at.strftime("%Y-%m-%d %H:%M:%S") if ro.created_at else None,
            }
        )
    return out


def execution_board(db: Session, ro_id: int) -> dict:
    ro = get_ro(db, ro_id)
    _recalc_ro_costs(db, ro)
    attachments = (
        db.query(Attachment)
        .filter(
            Attachment.entity_type == "repair_order",
            Attachment.entity_id == ro.id,
            Attachment.deleted_at.is_(None),
        )
        .order_by(Attachment.id.desc())
        .limit(50)
        .all()
    )
    faults = (
        db.query(RepairFault)
        .filter(RepairFault.repair_order_id == ro.id, RepairFault.deleted_at.is_(None))
        .order_by(RepairFault.id.desc())
        .all()
    )
    time_entries = (
        db.query(RepairTimeEntry)
        .filter(
            RepairTimeEntry.repair_order_id == ro.id,
            RepairTimeEntry.deleted_at.is_(None),
        )
        .order_by(RepairTimeEntry.id.desc())
        .limit(200)
        .all()
    )
    variations = (
        db.query(Variation)
        .options(joinedload(Variation.lines))
        .filter(Variation.repair_order_id == ro.id, Variation.deleted_at.is_(None))
        .order_by(Variation.id.desc())
        .all()
    )
    var_by_id = {v.id: v for v in variations}
    fault_rows = [_fault_row(db, f, var_by_id.get(f.variation_id) if f.variation_id else None) for f in faults]
    return {
        "repair_order": {
            "id": ro.id,
            "document_no": ro.document_no,
            "customer_name": ro.customer_name,
            "customer_phone": ro.customer_phone,
            "customer_address": ro.customer_address,
            "customer_reg_no": ro.customer_reg_no,
            "customer_made": ro.customer_made,
            "customer_mileage": ro.customer_mileage,
            "customer_vin": ro.customer_vin,
            "customer_color": ro.customer_color,
            "problem_description": ro.problem_description,
            "diagnosis_plan": ro.diagnosis_plan,
            "notes": ro.notes,
            "current_status": ro.current_status,
            "worker_id": ro.worker_id,
            "worker_name": ro.worker_name,
            "due_at": ro.due_at.strftime("%Y-%m-%d %H:%M:%S") if ro.due_at else None,
            "submitted_for_qc_at": (
                ro.submitted_for_qc_at.strftime("%Y-%m-%d %H:%M:%S")
                if ro.submitted_for_qc_at
                else None
            ),
            "labour_cost_total": float(ro.labour_cost_total or 0),
            "parts_cost_total": float(ro.parts_cost_total or 0),
            "job_cost_total": float(ro.labour_cost_total or 0) + float(ro.parts_cost_total or 0),
            "qc_signoff_id": ro.qc_signoff_id,
            "branch_id": ro.branch_id,
            "version": ro.version,
        },
        "progress": _progress(ro),
        "labour": [_labour_dict(db, l) for l in (ro.labour or [])],
        "parts": [_part_dict(db, p) for p in (ro.parts or [])],
        "faults": fault_rows,
        "time_entries": [t.to_dict() for t in time_entries],
        "attachments": [a.to_dict() for a in attachments],
        "variations": [v.to_dict() for v in variations],
        "next_action": next_action(db, repair_order_id=ro.id),
        "payroll_note": (
            "Repair time entries update job labour cost only. "
            "Payroll hours come from attendance / ZKTeco and stay separate."
        ),
    }


def start_labour(db: Session, ro: RepairOrder, labour_id: int, user, *, worker_id: int | None = None) -> dict:
    _assert_ro_open(ro)
    lab = get_labour(db, ro, labour_id)
    _assert_labour_workable(db, lab)
    if _open_time_entry(db, lab.id):
        raise HTTPException(
            status_code=409,
            detail="Time already running on this task — pause or complete first (duplicate entry blocked)",
        )
    now = _now()
    entry = RepairTimeEntry(
        repair_order_id=ro.id,
        labour_id=lab.id,
        worker_id=worker_id or lab.assigned_worker_id or ro.worker_id,
        started_at=now,
        status="open",
        hours=0.0,
        created_by_user=getattr(user, "username", None),
        branch_id=ro.branch_id,
    )
    db.add(entry)
    lab.status = "in_progress"
    if not lab.started_at:
        lab.started_at = now
    lab.paused_at = None
    if (ro.current_status or "").lower() in ("received", "waiting_parts"):
        ro.current_status = "in_progress"
    db.flush()
    audit_write(
        db,
        user=user,
        action="TIME_START",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Started labour #{lab.id}",
        new_value={"labour_id": lab.id, "entry_id": entry.id},
    )
    return {"entry": entry.to_dict(), "labour": _labour_dict(db, lab)}


def pause_labour(db: Session, ro: RepairOrder, labour_id: int, user) -> dict:
    lab = get_labour(db, ro, labour_id)
    entry = _open_time_entry(db, lab.id)
    if not entry:
        raise HTTPException(status_code=400, detail="No running time entry to pause")
    hours = _close_entry(entry)
    lab.actual_hours = float(lab.actual_hours or 0) + hours
    lab.status = "paused"
    lab.paused_at = _now()
    _recalc_labour_cost(db, lab)
    _recalc_ro_costs(db, ro)
    db.flush()
    audit_write(
        db,
        user=user,
        action="TIME_PAUSE",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Paused labour #{lab.id} (+{hours}h)",
        new_value={"labour_id": lab.id, "hours_added": hours, "actual_hours": lab.actual_hours},
    )
    return {"entry": entry.to_dict(), "labour": _labour_dict(db, lab)}


def resume_labour(db: Session, ro: RepairOrder, labour_id: int, user, *, worker_id: int | None = None) -> dict:
    lab = get_labour(db, ro, labour_id)
    st = (lab.status or "").lower()
    if st not in ("paused", "in_progress", "approved", "pending"):
        if st in _DONE:
            raise HTTPException(status_code=400, detail="Cannot resume a completed task")
    return start_labour(db, ro, labour_id, user, worker_id=worker_id)


def record_manual_hours(
    db: Session,
    ro: RepairOrder,
    labour_id: int,
    user,
    *,
    hours: float,
    notes: str | None = None,
    replace: bool = False,
) -> dict:
    """Add hours (or set total hours). Auto-pauses a running clock first."""
    _assert_ro_open(ro)
    lab = get_labour(db, ro, labour_id)
    _assert_labour_workable(db, lab)
    try:
        hours = float(hours)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="hours must be a number") from exc
    if hours <= 0:
        raise HTTPException(status_code=400, detail="Enter hours greater than 0")
    if hours > 24 and not replace:
        raise HTTPException(status_code=400, detail="Single entry cannot exceed 24 hours")
    if replace and hours > 100:
        raise HTTPException(status_code=400, detail="Total hours cannot exceed 100")

    open_entry = _open_time_entry(db, lab.id)
    auto_paused = 0.0
    if open_entry:
        auto_paused = _close_entry(open_entry)
        lab.actual_hours = float(lab.actual_hours or 0) + auto_paused
        lab.status = "paused"
        lab.paused_at = _now()

    now = _now()
    if replace:
        previous = float(lab.actual_hours or 0)
        lab.actual_hours = round(hours, 4)
        entry = RepairTimeEntry(
            repair_order_id=ro.id,
            labour_id=lab.id,
            worker_id=lab.assigned_worker_id or ro.worker_id,
            started_at=now,
            ended_at=now,
            status="closed",
            hours=round(hours, 4),
            notes=notes or f"Set total hours (was {previous})",
            created_by_user=getattr(user, "username", None),
            branch_id=ro.branch_id,
        )
    else:
        entry = RepairTimeEntry(
            repair_order_id=ro.id,
            labour_id=lab.id,
            worker_id=lab.assigned_worker_id or ro.worker_id,
            started_at=now,
            ended_at=now,
            status="closed",
            hours=round(hours, 4),
            notes=notes,
            created_by_user=getattr(user, "username", None),
            branch_id=ro.branch_id,
        )
        lab.actual_hours = float(lab.actual_hours or 0) + float(hours)

    db.add(entry)
    if not lab.started_at:
        lab.started_at = now
    # Never leave a clock open after manual entry. If we auto-paused, stay paused.
    st = (lab.status or "").lower()
    if auto_paused > 0 or st == "paused":
        lab.status = "paused"
        lab.paused_at = lab.paused_at or now
    elif st in ("pending", "approved"):
        lab.status = "in_progress"
        lab.paused_at = None
    _recalc_labour_cost(db, lab)
    _recalc_ro_costs(db, ro)
    db.flush()
    audit_write(
        db,
        user=user,
        action="TIME_RECORD",
        module="repair_execution",
        reference_id=ro.id,
        details=(
            f"{'Set' if replace else 'Added'} {hours}h on labour #{lab.id}"
            + (f" (auto-paused {auto_paused}h)" if auto_paused else "")
        ),
        new_value={
            "labour_id": lab.id,
            "hours": hours,
            "replace": replace,
            "actual_hours": lab.actual_hours,
        },
    )
    return {
        "entry": entry.to_dict(),
        "labour": _labour_dict(db, lab),
        "auto_paused_hours": auto_paused,
    }


def complete_labour(db: Session, ro: RepairOrder, labour_id: int, user, *, notes: str | None = None) -> dict:
    _assert_ro_open(ro)
    lab = get_labour(db, ro, labour_id)
    _assert_labour_workable(db, lab)
    entry = _open_time_entry(db, lab.id)
    if entry:
        hours = _close_entry(entry)
        lab.actual_hours = float(lab.actual_hours or 0) + hours
    lab.status = "done"
    lab.completed_at = _now()
    if notes:
        lab.line_notes = ((lab.line_notes or "") + "\n" + notes).strip()
    _recalc_labour_cost(db, lab)
    _recalc_ro_costs(db, ro)
    db.flush()
    audit_write(
        db,
        user=user,
        action="LABOUR_DONE",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Completed labour #{lab.id}",
        new_value=_labour_dict(db, lab),
    )
    return {"labour": _labour_dict(db, lab)}


def add_labour_note(db: Session, ro: RepairOrder, labour_id: int, user, note: str) -> dict:
    lab = get_labour(db, ro, labour_id)
    if not (note or "").strip():
        raise HTTPException(status_code=400, detail="note is required")
    lab.line_notes = ((lab.line_notes or "") + "\n" + note.strip()).strip()
    audit_write(
        db,
        user=user,
        action="NOTE",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Note on labour #{lab.id}",
    )
    return {"labour": _labour_dict(db, lab)}


def request_parts(db: Session, ro: RepairOrder, data: dict, user) -> dict:
    """Request additional parts. Customer-billable extras must go through variation."""
    _assert_ro_open(ro)
    bill_customer = bool(data.get("bill_customer", True))
    if bill_customer:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Customer-billable parts require the variation / approval process",
                "use": "POST /repair-orders/{id}/execution/faults or /variations",
            },
        )
    inventory_id = data.get("inventory_id")
    qty = int(data.get("quantity") or 1)
    if qty <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    desc = (data.get("description") or "").strip()
    inv = None
    if inventory_id:
        inv = db.get(Inventory, int(inventory_id))
        if not inv or inv.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Inventory item not found")
        desc = desc or inv.name
    if not desc:
        raise HTTPException(status_code=400, detail="description is required")
    part = RepairOrderPart(
        repair_order_id=ro.id,
        inventory_id=inv.id if inv else None,
        description=desc,
        part_number=inv.part_number if inv else data.get("part_number"),
        quantity=qty,
        status="requested",
        qty_reserved=0,
        qty_issued=0,
        qty_returned=0,
        ownership_type=data.get("ownership_type") or "shop_stock",
        approval_status="approved",  # internal / warranty path
        unit_cost=float(inv.avg_cost) if inv and inv.avg_cost is not None else None,
        branch_id=ro.branch_id,
    )
    db.add(part)
    if (ro.current_status or "").lower() == "in_progress":
        ro.current_status = "waiting_parts"
    db.flush()
    audit_write(
        db,
        user=user,
        action="PARTS_REQUEST",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Requested {qty} × {desc}",
        new_value=_part_dict(db, part),
    )
    return {"part": _part_dict(db, part)}


def _ensure_stock_audit_reason(ro: RepairOrder, *, action: str) -> None:
    """Inventory.quantity changes require X-Audit-Reason via foundation hooks."""
    from app.foundation.context import get_reason, set_reason

    if (get_reason() or "").strip():
        return
    set_reason(f"{action} for RO #{ro.id}")


def issue_parts(
    db: Session,
    ro: RepairOrder,
    part_id: int,
    user,
    *,
    qty: int | None = None,
    from_reserve: bool | None = None,
) -> dict:
    """Issue stock to RO part line. Prevents over-issue / duplicate deduction."""
    _assert_ro_open(ro)
    part = get_part(db, ro, part_id)
    _assert_part_workable(db, part)
    if (part.ownership_type or "shop_stock") == "customer_supplied":
        raise HTTPException(status_code=400, detail="Customer-supplied parts are not deducted from stock")
    if not part.inventory_id:
        raise HTTPException(status_code=400, detail="Part has no inventory link")
    remaining = max(0, int(part.quantity or 0) - int(part.qty_issued or 0))
    amount = int(qty) if qty is not None else remaining
    if amount <= 0:
        raise HTTPException(
            status_code=409,
            detail="Nothing left to issue (already fully issued — duplicate deduction blocked)",
        )
    if amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot issue {amount}: only {remaining} remaining on this line",
        )
    inv = db.get(Inventory, part.inventory_id)
    if not inv or inv.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    use_reserve = from_reserve if from_reserve is not None else int(inv.reserved or 0) >= amount
    _ensure_stock_audit_reason(ro, action="Issue parts")
    try:
        txn = issue_to_ro(
            db,
            item=inv,
            qty=amount,
            repair_order_id=ro.id,
            created_by=getattr(user, "id", None),
            notes=f"Execution issue part #{part.id}",
            from_reserve=use_reserve,
        )
    except StockError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    part.qty_issued = int(part.qty_issued or 0) + amount
    part.status = "issued" if part.qty_issued >= int(part.quantity or 0) else "partial"
    if part.unit_cost is None and inv.avg_cost is not None:
        part.unit_cost = float(inv.avg_cost)
    _recalc_ro_costs(db, ro)
    if (ro.current_status or "").lower() == "waiting_parts":
        ro.current_status = "in_progress"
    db.flush()
    audit_write(
        db,
        user=user,
        action="PARTS_ISSUE",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Issued {amount} of part #{part.id}",
        new_value={"part": _part_dict(db, part), "txn_id": txn.id},
    )
    return {"part": _part_dict(db, part), "transaction_id": txn.id}


def return_parts(db: Session, ro: RepairOrder, part_id: int, user, *, qty: int | None = None) -> dict:
    part = get_part(db, ro, part_id)
    if (part.ownership_type or "shop_stock") == "customer_supplied":
        raise HTTPException(status_code=400, detail="Customer-supplied parts are not returned to stock")
    if not part.inventory_id:
        raise HTTPException(status_code=400, detail="Part has no inventory link")
    returnable = max(0, int(part.qty_issued or 0) - int(part.qty_returned or 0))
    amount = int(qty) if qty is not None else returnable
    if amount <= 0:
        raise HTTPException(
            status_code=409,
            detail="Nothing to return (already fully returned — duplicate blocked)",
        )
    if amount > returnable:
        raise HTTPException(status_code=400, detail=f"Cannot return {amount}: only {returnable} returnable")
    inv = db.get(Inventory, part.inventory_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    _ensure_stock_audit_reason(ro, action="Return unused parts")
    try:
        txn = return_from_ro(
            db,
            item=inv,
            qty=amount,
            repair_order_id=ro.id,
            created_by=getattr(user, "id", None),
            notes=f"Execution return part #{part.id}",
        )
    except StockError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    part.qty_returned = int(part.qty_returned or 0) + amount
    if part.qty_returned >= int(part.qty_issued or 0):
        part.status = "returned"
    _recalc_ro_costs(db, ro)
    db.flush()
    audit_write(
        db,
        user=user,
        action="PARTS_RETURN",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Returned {amount} of part #{part.id}",
        new_value=_part_dict(db, part),
    )
    return {"part": _part_dict(db, part), "transaction_id": txn.id}


def _fault_editable(fault: RepairFault, var: Variation | None) -> bool:
    st = (fault.status or "").lower()
    if st in ("approved", "added", "promoted", "rejected", "cancelled"):
        return False
    if var is None:
        return True
    return (var.status or "").lower() in ("draft", "cancelled")


def _variation_on_ro(db: Session, repair_order_id: int, var: Variation | None) -> bool:
    """True when approved variation lines were already promoted onto the RO."""
    if not var:
        return False
    if (
        db.query(RepairOrderLabour)
        .filter(
            RepairOrderLabour.repair_order_id == repair_order_id,
            RepairOrderLabour.from_variation_id == var.id,
            RepairOrderLabour.deleted_at.is_(None),
        )
        .first()
    ):
        return True
    return (
        db.query(RepairOrderPart)
        .filter(
            RepairOrderPart.repair_order_id == repair_order_id,
            RepairOrderPart.from_variation_id == var.id,
            RepairOrderPart.deleted_at.is_(None),
        )
        .first()
        is not None
    )


def _approval_url_for_variation(db: Session, var: Variation | None) -> str | None:
    """Latest non-revoked public approve path for this variation quote."""
    if not var or not var.quote_invoice_id:
        return None
    tok = (
        db.query(ApprovalToken)
        .filter(
            ApprovalToken.invoice_id == var.quote_invoice_id,
            ApprovalToken.revoked_at.is_(None),
        )
        .order_by(ApprovalToken.id.desc())
        .first()
    )
    if not tok or not tok.token:
        return None
    if tok.expires_at and tok.expires_at < datetime.utcnow():
        return None
    return f"/approve/{tok.token}"


def _fault_row(db: Session, fault: RepairFault, var: Variation | None = None) -> dict:
    if var is None and fault.variation_id:
        var = db.get(Variation, fault.variation_id)
        if var and var.deleted_at is not None:
            var = None
    estimated = 0.0
    lines: list[dict] = []
    if var:
        lines = [
            ln.to_dict()
            for ln in (var.lines or [])
            if getattr(ln, "deleted_at", None) is None
        ]
        estimated = sum(
            float(ln.get("unit_price") or 0) * int(ln.get("quantity") or 1) for ln in lines
        )
    approval_path = _approval_url_for_variation(db, var)
    added = (fault.status or "").lower() in ("added", "promoted") or _variation_on_ro(
        db, fault.repair_order_id, var
    )
    var_st = (var.status or "").lower() if var else ""
    data = fault.to_dict()
    data.update(
        {
            "estimated_price": estimated,
            "variation_status": var.status if var else None,
            "variation_lines": lines,
            "editable": _fault_editable(fault, var),
            "deletable": _fault_editable(fault, var),
            "can_send": bool(var and var_st == "draft"),
            "can_promote": bool(
                var and var_st in ("approved", "partially_approved") and not added
            ),
            "added_to_job": added,
            "approval_url": approval_path,
            "quote_invoice_id": var.quote_invoice_id if var else None,
        }
    )
    return data


def get_fault(db: Session, ro: RepairOrder, fault_id: int) -> RepairFault:
    fault = db.get(RepairFault, fault_id)
    if not fault or fault.repair_order_id != ro.id or fault.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Fault not found")
    return fault


def record_fault(db: Session, ro: RepairOrder, data: dict, user) -> dict:
    """Record additional fault and open a variation for customer approval."""
    _assert_ro_open(ro)
    desc = (data.get("description") or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="description is required")
    lines = data.get("lines") or [
        {
            "line_type": "labour",
            "description": desc,
            "quantity": 1,
            "unit_price": float(data.get("estimated_price") or 0),
            "labour_code_id": data.get("labour_code_id"),
        }
    ]
    var = create_variation(
        db,
        ro,
        {"notes": f"Additional fault: {desc}", "lines": lines},
        user,
    )
    fault = RepairFault(
        repair_order_id=ro.id,
        description=desc,
        severity=(data.get("severity") or "normal").lower(),
        status="awaiting_approval",
        variation_id=var.id,
        photo_attachment_id=data.get("photo_attachment_id"),
        recorded_by=getattr(user, "username", None),
        branch_id=ro.branch_id,
    )
    db.add(fault)
    db.flush()
    audit_write(
        db,
        user=user,
        action="FAULT",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Fault → variation #{var.id}",
        new_value=fault.to_dict(),
    )
    return {"fault": _fault_row(db, fault, var), "variation": var.to_dict()}


def update_fault(db: Session, ro: RepairOrder, fault_id: int, data: dict, user) -> dict:
    """Edit draft fault description / estimated price before customer send."""
    _assert_ro_open(ro)
    fault = get_fault(db, ro, fault_id)
    var = db.get(Variation, fault.variation_id) if fault.variation_id else None
    if var and var.deleted_at is not None:
        var = None
    if not _fault_editable(fault, var):
        raise HTTPException(
            status_code=400,
            detail="Cannot edit after customer approval has started",
        )
    desc = data.get("description")
    if desc is not None:
        desc = str(desc).strip()
        if not desc:
            raise HTTPException(status_code=400, detail="description is required")
        fault.description = desc
        if var:
            var.notes = f"Additional fault: {desc}"
            for ln in var.lines or []:
                if (ln.line_type or "labour").lower() == "labour" and not ln.deleted_at:
                    ln.description = desc
                    break
    if "estimated_price" in data and var:
        price = float(data.get("estimated_price") or 0)
        if price < 0:
            raise HTTPException(status_code=400, detail="price cannot be negative")
        updated = False
        for ln in var.lines or []:
            if ln.deleted_at is not None:
                continue
            ln.unit_price = price
            updated = True
            break
        if not updated:
            db.add(
                VariationLine(
                    variation_id=var.id,
                    line_type="labour",
                    description=fault.description,
                    quantity=1,
                    unit_price=price,
                    approval_status="pending",
                    branch_id=ro.branch_id,
                )
            )
    if data.get("severity"):
        fault.severity = str(data["severity"]).lower()
    db.flush()
    audit_write(
        db,
        user=user,
        action="FAULT_UPDATE",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Updated fault #{fault.id}",
        new_value=_fault_row(db, fault, var),
    )
    return {"fault": _fault_row(db, fault, var)}


def delete_fault(db: Session, ro: RepairOrder, fault_id: int, user) -> dict:
    """Soft-delete a draft fault and its draft variation."""
    _assert_ro_open(ro)
    fault = get_fault(db, ro, fault_id)
    var = db.get(Variation, fault.variation_id) if fault.variation_id else None
    if var and var.deleted_at is not None:
        var = None
    if not _fault_editable(fault, var):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete after customer approval has started",
        )
    soft_delete(fault, by=getattr(user, "username", None))
    fault.status = "cancelled"
    if var:
        soft_delete(var, by=getattr(user, "username", None))
        var.status = "cancelled"
        for ln in var.lines or []:
            if ln.deleted_at is None:
                soft_delete(ln, by=getattr(user, "username", None))
    audit_write(
        db,
        user=user,
        action="FAULT_DELETE",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Deleted fault #{fault.id}",
    )
    return {"ok": True, "id": fault_id}


def promote_variation(db: Session, ro: RepairOrder, variation_id: int, user) -> dict:
    """Promote customer-approved variation lines onto the RO for work + stock."""
    _assert_ro_open(ro)
    var = db.get(Variation, variation_id)
    if not var or var.repair_order_id != ro.id or var.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Variation not found")
    added_labour: list[dict] = []
    added_parts: list[dict] = []
    for ln in var.lines or []:
        if (ln.approval_status or "").lower() != "approved":
            continue
        if ln.line_type == "part":
            # Skip if already promoted
            exists = (
                db.query(RepairOrderPart)
                .filter(
                    RepairOrderPart.repair_order_id == ro.id,
                    RepairOrderPart.from_variation_id == var.id,
                    RepairOrderPart.description == ln.description,
                    RepairOrderPart.deleted_at.is_(None),
                )
                .first()
            )
            if exists:
                continue
            part = RepairOrderPart(
                repair_order_id=ro.id,
                inventory_id=ln.inventory_id,
                description=ln.description,
                quantity=int(ln.quantity or 1),
                status="pending",
                from_variation_id=var.id,
                approval_status="approved",
                ownership_type="shop_stock",
                branch_id=ro.branch_id,
            )
            if ln.inventory_id:
                inv = db.get(Inventory, ln.inventory_id)
                if inv:
                    part.part_number = inv.part_number
                    part.unit_cost = float(inv.avg_cost) if inv.avg_cost is not None else None
            db.add(part)
            db.flush()
            if part.inventory_id:
                try:
                    issue_parts(db, ro, part.id, user)
                except HTTPException:
                    # Leave as pending if stock insufficient — still promoted
                    pass
            added_parts.append(_part_dict(db, part))
        else:
            exists = (
                db.query(RepairOrderLabour)
                .filter(
                    RepairOrderLabour.repair_order_id == ro.id,
                    RepairOrderLabour.from_variation_id == var.id,
                    RepairOrderLabour.description == ln.description,
                    RepairOrderLabour.deleted_at.is_(None),
                )
                .first()
            )
            if exists:
                continue
            code = db.get(LabourCode, ln.labour_code_id) if ln.labour_code_id else None
            # Variation unit_price is the quoted amount; use as hourly rate with 1 std hour
            # when no labour catalogue code is linked (avoids 0 PKR/h on promoted faults).
            quoted = float(ln.unit_price or 0)
            lab = RepairOrderLabour(
                repair_order_id=ro.id,
                description=ln.description,
                status="Approved",
                labour_code_id=ln.labour_code_id,
                from_variation_id=var.id,
                approval_status="approved",
                std_hours=code.standard_hours if code else (1.0 if quoted else None),
                labour_rate=float(code.rate) if code else (quoted if quoted else None),
                branch_id=ro.branch_id,
            )
            db.add(lab)
            db.flush()
            added_labour.append(_labour_dict(db, lab))
    # Sync fault status — visible as "Added" in the workbench
    for fault in (
        db.query(RepairFault)
        .filter(RepairFault.variation_id == var.id, RepairFault.deleted_at.is_(None))
        .all()
    ):
        fault.status = "added"
    if not added_labour and not added_parts:
        raise HTTPException(
            status_code=400,
            detail="No approved variation lines to promote (or already promoted)",
        )
    _recalc_ro_costs(db, ro)
    audit_write(
        db,
        user=user,
        action="VARIATION_PROMOTE",
        module="repair_execution",
        reference_id=ro.id,
        details=f"Promoted variation #{var.id}",
        new_value={"labour": added_labour, "parts": added_parts},
    )
    return {"labour": added_labour, "parts": added_parts}


def submit_for_inspection(db: Session, ro: RepairOrder, user, *, notes: str | None = None) -> dict:
    """Mark work ready for QC. Blocks if unapproved variation work is in progress."""
    _assert_ro_open(ro)
    for lab in ro.labour or []:
        approval = (lab.approval_status or "approved").lower()
        if lab.from_variation_id and approval != "approved":
            st = (lab.status or "").lower()
            if st in ("in_progress", "paused", "done", "complete", "completed"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Labour #{lab.id} worked without approval — cannot submit",
                )
    incomplete = [
        l
        for l in (ro.labour or [])
        if (l.approval_status or "approved").lower() == "approved"
        and (l.status or "").lower() not in _DONE
    ]
    if incomplete:
        raise HTTPException(
            status_code=400,
            detail=f"{len(incomplete)} approved labour task(s) still incomplete",
        )
    # Close any stray open clocks
    for lab in ro.labour or []:
        entry = _open_time_entry(db, lab.id)
        if entry:
            hours = _close_entry(entry)
            lab.actual_hours = float(lab.actual_hours or 0) + hours
            _recalc_labour_cost(db, lab)
    _recalc_ro_costs(db, ro)
    ro.submitted_for_qc_at = _now()
    ro.current_status = "awaiting_qc"
    if notes:
        ro.notes = ((ro.notes or "") + "\n" + notes).strip()
    db.flush()
    audit_write(
        db,
        user=user,
        action="SUBMIT_QC",
        module="repair_execution",
        reference_id=ro.id,
        details="Submitted for inspection",
        new_value={
            "submitted_for_qc_at": ro.submitted_for_qc_at.isoformat(),
            "labour_cost_total": ro.labour_cost_total,
            "parts_cost_total": ro.parts_cost_total,
        },
    )
    return {
        "repair_order_id": ro.id,
        "current_status": ro.current_status,
        "submitted_for_qc_at": ro.submitted_for_qc_at.strftime("%Y-%m-%d %H:%M:%S"),
        "labour_cost_total": float(ro.labour_cost_total or 0),
        "parts_cost_total": float(ro.parts_cost_total or 0),
        "job_cost_total": float(ro.labour_cost_total or 0) + float(ro.parts_cost_total or 0),
        "next_action": next_action(db, repair_order_id=ro.id),
    }


def update_ro_notes(db: Session, ro: RepairOrder, user, notes: str) -> dict:
    ro.notes = notes
    audit_write(
        db,
        user=user,
        action="NOTES",
        module="repair_execution",
        reference_id=ro.id,
        details="Updated RO notes",
    )
    return {"notes": ro.notes}
