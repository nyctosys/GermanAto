"""Role-scoped home dashboard built from live DB aggregates.

Revenue (invoiced sales) is kept separate from cash receipts, cash/bank
balances, receivables, and liabilities. Values are never fabricated.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.invoice_math import invoice_amount_due, invoice_amount_paid
from app.models import (
    AttendanceRecord,
    CashReceived,
    Expense,
    YardGatePass,
    Inventory,
    Invoice,
    PurchaseOrder,
    RepairOrder,
    Vendor,
    VendorLedger,
    Worker,
)
from app.security import ADMIN_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS
from app.models import RolePermission

logger = logging.getLogger(__name__)

# Soft-delete guard for raw SQL (foundation columns).
_LIVE = "(deleted_at IS NULL)"

OVERDUE_DAYS = 7

# Map app roles → dashboard view profiles the UI can specialize on.
ROLE_VIEWS = {
    "admin": "manager",
    "owner": "manager",
    "manager": "manager",
    "accountant": "accountant",
    "service_advisor": "receptionist",
    "technician": "technician",
    "store_keeper": "storekeeper",
    "inventory_manager": "storekeeper",
}

# Section → permission that must be present to include it.
SECTION_PERMISSIONS: dict[str, str] = {
    "finance": "reports",
    "cash": "daily-expenses",
    "expenses": "daily-expenses",
    "invoices": "invoice",
    "quotes": "invoice",
    "repairs": "repair-order",
    "inventory": "inventory",
    "vendors": "vendors",
    "hr": "hr",
    "cars": "car",
    "gate_passes": "car",
}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _f(value: Any) -> float:
    return float(value or 0)


def _i(value: Any) -> int:
    return int(value or 0)


def resolve_date_range(
    period: str | None,
    start_date_param: str | None,
    end_date_param: str | None,
) -> tuple[date, date, str]:
    today = date.today()
    if start_date_param and end_date_param:
        try:
            start = datetime.strptime(start_date_param.strip(), "%Y-%m-%d").date()
            end = datetime.strptime(end_date_param.strip(), "%Y-%m-%d").date()
            if start <= end:
                return start, end, "custom"
        except (ValueError, TypeError):
            pass

    period = (period or "month").lower()
    if period == "day":
        return today, today, "day"
    if period == "week":
        return today - timedelta(days=6), today, "week"
    if period == "year":
        return today.replace(month=1, day=1), today, "year"
    return today.replace(day=1), today, "month"


def user_permissions(db: Session, user) -> set[str]:
    if user.role in ("admin", "owner"):
        return set(ADMIN_PERMISSIONS)
    perms = [p.permission for p in db.query(RolePermission).filter_by(role=user.role).all()]
    if not perms and db.query(RolePermission).first() is None:
        perms = DEFAULT_ROLE_PERMISSIONS.get(user.role, [])
    return set(perms)


def _can(permissions: set[str], section: str) -> bool:
    need = SECTION_PERMISSIONS.get(section)
    return need is None or need in permissions


def _kpi(label: str, value: Any, *, href: str, meta: str | None = None, alert: bool = False, kind: str = "number"):
    return {
        "label": label,
        "value": value,
        "href": href,
        "meta": meta,
        "alert": alert,
        "kind": kind,  # money | number
    }


# ---------- Finance builders ----------

def _revenue(db: Session, start: date, end: date) -> dict:
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    row = db.execute(
        text(
            f"""
            SELECT COALESCE(SUM(net_total), 0), COUNT(*)
            FROM invoice
            WHERE type_of = 'invoice'
              AND {_LIVE}
              AND created_at >= :start AND created_at <= :end
            """
        ),
        {"start": start_dt, "end": end_dt},
    ).fetchone()
    daily = db.execute(
        text(
            f"""
            SELECT DATE(created_at) AS d, COALESCE(SUM(net_total), 0)
            FROM invoice
            WHERE type_of = 'invoice'
              AND {_LIVE}
              AND created_at >= :start AND created_at <= :end
            GROUP BY DATE(created_at)
            ORDER BY d
            """
        ),
        {"start": start_dt, "end": end_dt},
    ).fetchall()
    return {
        "total": _f(row[0]),
        "count": _i(row[1]),
        "daily": [{"date": str(r[0]), "total": _f(r[1])} for r in daily],
    }


def _cash_received(db: Session, start: date, end: date) -> dict:
    row = db.execute(
        text(
            f"""
            SELECT COALESCE(SUM(amount), 0), COUNT(*)
            FROM cash_received
            WHERE {_LIVE}
              AND date >= :start AND date <= :end
            """
        ),
        {"start": start, "end": end},
    ).fetchone()
    by_method = db.execute(
        text(
            f"""
            SELECT COALESCE(payment_method, 'Unspecified'), COALESCE(SUM(amount), 0)
            FROM cash_received
            WHERE {_LIVE}
              AND date >= :start AND date <= :end
            GROUP BY COALESCE(payment_method, 'Unspecified')
            """
        ),
        {"start": start, "end": end},
    ).fetchall()
    daily = db.execute(
        text(
            f"""
            SELECT date, COALESCE(SUM(amount), 0)
            FROM cash_received
            WHERE {_LIVE}
              AND date >= :start AND date <= :end
            GROUP BY date
            ORDER BY date
            """
        ),
        {"start": start, "end": end},
    ).fetchall()
    recent = (
        db.query(CashReceived)
        .filter(CashReceived.date >= start, CashReceived.date <= end)
        .order_by(CashReceived.date.desc(), CashReceived.id.desc())
        .limit(10)
        .all()
    )
    return {
        "total": _f(row[0]),
        "count": _i(row[1]),
        "by_method": [{"method": r[0], "total": _f(r[1])} for r in by_method],
        "daily": [{"date": str(r[0]), "total": _f(r[1])} for r in daily],
        "recent": [
            {
                "id": c.id,
                "date": _iso(c.date),
                "description": c.description,
                "amount": _f(c.amount),
                "payment_method": c.payment_method,
                "invoice_id": c.invoice_id,
            }
            for c in recent
        ],
    }


def _expenses(db: Session, start: date, end: date) -> dict:
    today = date.today()
    row = db.execute(
        text(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN date = :today THEN amount END), 0),
                COALESCE(SUM(amount), 0),
                COUNT(*)
            FROM expense
            WHERE {_LIVE}
              AND date >= :start AND date <= :end
            """
        ),
        {"today": today, "start": start, "end": end},
    ).fetchone()
    daily = db.execute(
        text(
            f"""
            SELECT date, COALESCE(SUM(amount), 0)
            FROM expense
            WHERE {_LIVE}
              AND date >= :start AND date <= :end
            GROUP BY date
            ORDER BY date
            """
        ),
        {"start": start, "end": end},
    ).fetchall()
    recent = (
        db.query(Expense)
        .filter(Expense.date >= start, Expense.date <= end)
        .order_by(Expense.date.desc(), Expense.id.desc())
        .limit(10)
        .all()
    )
    return {
        "today_total": _f(row[0]) if start <= today <= end else 0.0,
        "period_total": _f(row[1]),
        "count": _i(row[2]),
        "daily": [{"date": str(r[0]), "total": _f(r[1])} for r in daily],
        "recent": [
            {
                "id": e.id,
                "date": _iso(e.date),
                "category": e.category,
                "description": e.description,
                "amount": _f(e.amount),
            }
            for e in recent
        ],
    }


def _receivables(db: Session) -> dict:
    """Outstanding customer debt (assets). Advances already reduce owed."""
    invoices = (
        db.query(Invoice)
        .filter(Invoice.type_of == "invoice")
        .all()
    )
    items = []
    total = 0.0
    for inv in invoices:
        owed = invoice_amount_due(inv) - invoice_amount_paid(inv)
        owed = round(owed, 2)
        if owed <= 0:
            continue
        total += owed
        items.append(
            {
                "id": inv.id,
                "document_no": inv.document_no,
                "customer_name": inv.customer_name,
                "created_at": _iso(inv.created_at),
                "owed": owed,
                "status": inv.status,
            }
        )
    items.sort(key=lambda x: x["created_at"] or "")
    return {
        "total": round(total, 2),
        "count": len(items),
        "oldest": items[:8],
    }


def _customer_advances(db: Session) -> dict:
    """Liability: money held for customers (overpayment / quote advances)."""
    invoices = db.query(Invoice).all()
    credit = 0.0
    quote_adv = 0.0
    items: list[dict] = []
    for inv in invoices:
        paid = invoice_amount_paid(inv)
        if inv.type_of == "quote":
            adv = _f(inv.advance)
            if adv > 0:
                quote_adv += adv
                items.append(
                    {
                        "id": inv.id,
                        "kind": "quote_advance",
                        "customer_name": inv.customer_name,
                        "amount": adv,
                        "document_no": inv.document_no,
                    }
                )
            continue
        due = invoice_amount_due(inv)
        excess = round(paid - due, 2)
        if excess > 0:
            credit += excess
            items.append(
                {
                    "id": inv.id,
                    "kind": "overpayment",
                    "customer_name": inv.customer_name,
                    "amount": excess,
                    "document_no": inv.document_no,
                }
            )
    total = round(credit + quote_adv, 2)
    items.sort(key=lambda x: x["amount"], reverse=True)
    return {
        "total": total,
        "overpayments": round(credit, 2),
        "quote_advances": round(quote_adv, 2),
        "count": len(items),
        "items": items[:8],
    }


def _supplier_payables(db: Session) -> dict:
    """Latest ledger balance per vendor (running balance, not sum of rows)."""
    vendors = db.query(Vendor).all()
    items = []
    total = 0.0
    for v in vendors:
        last = (
            db.query(VendorLedger)
            .filter(VendorLedger.vendor_id == v.id)
            .order_by(VendorLedger.date.desc(), VendorLedger.id.desc())
            .first()
        )
        bal = _f(last.balance) if last else 0.0
        if bal <= 0:
            continue
        total += bal
        items.append(
            {
                "vendor_id": v.id,
                "vendor_name": v.name,
                "closing_balance": bal,
            }
        )
    items.sort(key=lambda x: x["closing_balance"], reverse=True)
    return {"total": round(total, 2), "count": len(items), "items": items[:10]}


def _cash_bank_balances(db: Session) -> dict:
    """Asset: till/bank position = all cash in − all expenses (ledger model)."""
    cash_total = _f(
        db.execute(text(f"SELECT COALESCE(SUM(amount), 0) FROM cash_received WHERE {_LIVE}")).scalar()
    )
    exp_total = _f(
        db.execute(text(f"SELECT COALESCE(SUM(amount), 0) FROM expense WHERE {_LIVE}")).scalar()
    )
    position = round(cash_total - exp_total, 2)

    by_method = db.execute(
        text(
            f"""
            SELECT COALESCE(payment_method, 'Unspecified'), COALESCE(SUM(amount), 0)
            FROM cash_received
            WHERE {_LIVE}
            GROUP BY COALESCE(payment_method, 'Unspecified')
            """
        )
    ).fetchall()
    methods = {str(r[0]).lower(): _f(r[1]) for r in by_method}

    cash_in = round(sum(v for k, v in methods.items() if k.strip() == "cash"), 2)
    bank_keys = ("bank", "transfer", "cheque", "check", "card", "online", "jazz", "easypaisa")
    bank_in = round(
        sum(v for k, v in methods.items() if any(x in k for x in bank_keys)),
        2,
    )
    other_in = round(max(0.0, cash_total - cash_in - bank_in), 2)

    return {
        "position": position,
        "total_in": cash_total,
        "total_out": exp_total,
        "cash_receipts": cash_in,
        "bank_receipts": bank_in,
        "other_receipts": other_in,
        "by_method": [{"method": r[0], "total": _f(r[1])} for r in by_method],
    }


# ---------- Operations builders ----------

def _quotes(db: Session) -> dict:
    pending = (
        db.query(Invoice)
        .filter(Invoice.type_of == "quote", Invoice.status == "pending")
        .order_by(Invoice.created_at.desc())
        .all()
    )
    value = sum(_f(q.net_total) for q in pending)
    return {
        "pending_count": len(pending),
        "pending_value": round(value, 2),
        "items": [
            {
                "id": q.id,
                "customer_name": q.customer_name,
                "total_amount": _f(q.net_total),
                "created_at": _iso(q.created_at),
                "quote_number": q.document_no or f"Q-{q.id:04d}",
                "status": q.status,
            }
            for q in pending[:10]
        ],
    }


def _repairs(db: Session) -> dict:
    open_ros = (
        db.query(RepairOrder)
        .filter(~RepairOrder.current_status.in_(("complete", "completed")))
        .order_by(RepairOrder.created_at.asc())
        .all()
    )
    by_status: dict[str, int] = {}
    for ro in open_ros:
        st = ro.current_status or "unknown"
        by_status[st] = by_status.get(st, 0) + 1

    today = date.today()
    done_today = (
        db.query(RepairOrder)
        .filter(
            RepairOrder.current_status.in_(("complete", "completed")),
            RepairOrder.updated_at >= datetime.combine(today, datetime.min.time()),
        )
        .count()
    )

    cutoff = datetime.combine(today - timedelta(days=OVERDUE_DAYS), datetime.min.time())
    overdue = [ro for ro in open_ros if ro.created_at and ro.created_at < cutoff]

    vehicles = []
    seen_plates: set[str] = set()
    for ro in open_ros:
        plate = (ro.customer_reg_no or "").strip().upper() or f"RO-{ro.id}"
        if plate in seen_plates:
            continue
        seen_plates.add(plate)
        vehicles.append(
            {
                "repair_order_id": ro.id,
                "plate": ro.customer_reg_no,
                "make": ro.customer_made,
                "customer_name": ro.customer_name,
                "status": ro.current_status,
                "worker_name": ro.worker_name,
                "created_at": _iso(ro.created_at),
            }
        )

    def _ro_row(ro: RepairOrder) -> dict:
        age = None
        if ro.created_at:
            age = (datetime.utcnow() - ro.created_at.replace(tzinfo=None)).days
        return {
            "id": ro.id,
            "document_no": ro.document_no,
            "customer_name": ro.customer_name,
            "customer_reg_no": ro.customer_reg_no,
            "status": ro.current_status,
            "worker_name": ro.worker_name,
            "created_at": _iso(ro.created_at),
            "age_days": age,
            "problem_description": (ro.problem_description or "")[:120],
        }

    return {
        "open_count": len(open_ros),
        "by_status": by_status,
        "completed_today": done_today,
        "overdue_count": len(overdue),
        "overdue_days": OVERDUE_DAYS,
        "overdue": [_ro_row(ro) for ro in overdue[:10]],
        "items": [_ro_row(ro) for ro in open_ros[:10]],
        "vehicles_in_workshop": vehicles[:20],
        "vehicles_count": len(vehicles),
    }


def _inventory(db: Session) -> dict:
    items = (
        db.query(Inventory)
        .filter(Inventory.quantity <= Inventory.reorder_level)
        .order_by(Inventory.quantity.asc())
        .all()
    )
    pending_po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.status.in_(("draft", "ordered", "partial")))
        .count()
    )
    return {
        "low_stock_count": len(items),
        "open_po_count": pending_po,
        "items": [
            {
                "id": i.id,
                "item_name": i.name,
                "part_number": i.part_number,
                "quantity": i.quantity,
                "reorder_level": i.reorder_level,
                "category": i.category,
                "urgency": "critical" if i.quantity <= (i.reorder_level or 0) * 0.5 else "warning",
            }
            for i in items[:10]
        ],
    }


def _hr(db: Session) -> dict:
    today = date.today()
    workers = db.query(Worker).filter(Worker.status == "active").all()
    attendance = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.date == today)
        .all()
    )
    by_worker = {a.worker_id: a for a in attendance}

    present = []
    available = []
    absent = []
    for w in workers:
        name = f"{w.first_name} {w.last_name}".strip()
        rec = by_worker.get(w.id)
        row = {
            "id": w.id,
            "employee_id": w.employee_id,
            "name": name,
            "position": w.position,
            "department": w.department,
        }
        if rec and rec.check_in_time and not rec.check_out_time:
            row["status"] = "on_site"
            row["check_in"] = _iso(rec.check_in_time)
            present.append(row)
        elif rec and rec.check_in_time:
            row["status"] = "checked_out"
            row["check_in"] = _iso(rec.check_in_time)
            row["check_out"] = _iso(rec.check_out_time)
            available.append(row)
        else:
            row["status"] = "not_checked_in"
            absent.append(row)

    return {
        "active_workers": len(workers),
        "present_count": len(present),
        "available_count": len(available),
        "absent_count": len(absent),
        "present": present[:15],
        "available": available[:15],
        "absent": absent[:15],
        "attendance_today": [
            {
                "id": a.id,
                "worker_id": a.worker_id,
                "worker_name": (
                    f"{a.worker.first_name} {a.worker.last_name}" if a.worker else None
                ),
                "check_in": _iso(a.check_in_time),
                "check_out": _iso(a.check_out_time),
                "work_hours": a.work_hours,
            }
            for a in attendance[:20]
        ],
    }


def _invoices_list(db: Session, start: date, end: date) -> dict:
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    rows = (
        db.query(Invoice)
        .filter(
            Invoice.type_of == "invoice",
            Invoice.created_at >= start_dt,
            Invoice.created_at <= end_dt,
        )
        .order_by(Invoice.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "count": len(rows),
        "items": [
            {
                "id": inv.id,
                "document_no": inv.document_no,
                "customer_name": inv.customer_name,
                "net_total": _f(inv.net_total),
                "status": inv.status,
                "created_at": _iso(inv.created_at),
                "owed": round(invoice_amount_due(inv) - invoice_amount_paid(inv), 2),
            }
            for inv in rows
        ],
    }


def _gate_passes(db: Session) -> dict:
    today = date.today()
    start_dt = datetime.combine(today, datetime.min.time())
    rows = (
        db.query(YardGatePass)
        .filter(YardGatePass.passed_at >= start_dt)
        .order_by(YardGatePass.passed_at.desc())
        .limit(15)
        .all()
    )
    recent = (
        db.query(YardGatePass)
        .order_by(YardGatePass.passed_at.desc())
        .limit(10)
        .all()
    )
    return {
        "today_count": len(rows),
        "in_today": sum(1 for g in rows if g.direction == "in"),
        "out_today": sum(1 for g in rows if g.direction == "out"),
        "recent": [g.to_dict() for g in recent],
    }


def _alerts(
    *,
    receivables: dict,
    repairs: dict,
    inventory: dict,
    quotes: dict,
    payables: dict,
    advances: dict,
) -> list[dict]:
    alerts = []
    if inventory["low_stock_count"]:
        alerts.append(
            {
                "level": "warning",
                "code": "low_stock",
                "message": f"{inventory['low_stock_count']} item(s) at or below reorder level",
                "href": "/inventory?low_stock=1",
            }
        )
    if repairs["overdue_count"]:
        alerts.append(
            {
                "level": "danger",
                "code": "overdue_jobs",
                "message": f"{repairs['overdue_count']} job(s) open longer than {OVERDUE_DAYS} days",
                "href": "/repair-orders?overdue=1",
            }
        )
    if receivables["count"]:
        alerts.append(
            {
                "level": "warning",
                "code": "receivables",
                "message": f"{receivables['count']} unpaid invoice(s) · Rs {receivables['total']:,.0f}",
                "href": "/invoices?status=unpaid",
            }
        )
    if quotes["pending_count"]:
        alerts.append(
            {
                "level": "info",
                "code": "pending_quotes",
                "message": f"{quotes['pending_count']} estimate(s) awaiting decision",
                "href": "/quotes/pending",
            }
        )
    if payables["count"]:
        alerts.append(
            {
                "level": "info",
                "code": "payables",
                "message": f"Supplier payables Rs {payables['total']:,.0f} across {payables['count']} vendor(s)",
                "href": "/vendors",
            }
        )
    if advances["total"] > 0:
        alerts.append(
            {
                "level": "info",
                "code": "advances",
                "message": f"Customer advances held Rs {advances['total']:,.0f}",
                "href": "/invoices",
            }
        )
    return alerts


def _quick_actions(permissions: set[str], view: str) -> list[dict]:
    catalog = [
        {"label": "New job card", "href": "/repair-orders/new", "permission": "repair-order", "views": None},
        {"label": "New estimate", "href": "/quotes/new", "permission": "invoice", "views": None},
        {"label": "New invoice", "href": "/invoices/new", "permission": "invoice", "views": None},
        {"label": "Record payment", "href": "/finance/cash-received", "permission": "daily-expenses", "views": None},
        {"label": "Record expense", "href": "/finance/daily-expenses", "permission": "daily-expenses", "views": None},
        {"label": "Purchase orders", "href": "/vendors", "permission": "vendors", "views": ("storekeeper", "manager", "accountant")},
        {"label": "Gate pass", "href": "/cars?gate_pass=1", "permission": "car", "views": ("receptionist", "manager", "technician")},
        {"label": "Attendance", "href": "/hr/attendance", "permission": "hr", "views": ("manager", "accountant")},
        {"label": "Low stock", "href": "/inventory?low_stock=1", "permission": "inventory", "views": ("storekeeper", "manager")},
        {"label": "Open repairs", "href": "/repair-orders", "permission": "repair-order", "views": ("technician", "receptionist", "manager")},
    ]
    out = []
    for a in catalog:
        if a["permission"] not in permissions:
            continue
        if a["views"] and view not in a["views"] and view != "manager":
            continue
        out.append({"label": a["label"], "href": a["href"]})
    return out


def build_dashboard(
    db: Session,
    user,
    *,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    permissions = user_permissions(db, user)
    view = ROLE_VIEWS.get(user.role, "receptionist")
    start, end, period_key = resolve_date_range(period, start_date, end_date)
    qs = f"start_date={start.isoformat()}&end_date={end.isoformat()}"

    sections: dict[str, Any] = {}
    failed: list[str] = []
    kpis: list[dict] = []

    def safe(name: str, fn):
        try:
            return fn()
        except Exception as e:
            db.rollback()
            logger.error("Dashboard section '%s' failed: %s", name, e)
            failed.append(name)
            return None

    # Permission helpers for each block
    finance_ok = _can(permissions, "finance") or _can(permissions, "cash")
    cash_ok = _can(permissions, "cash")
    invoice_ok = _can(permissions, "invoices")
    repair_ok = _can(permissions, "repairs")
    inv_ok = _can(permissions, "inventory")
    vendor_ok = _can(permissions, "vendors")
    hr_ok = _can(permissions, "hr")
    car_ok = _can(permissions, "cars")

    revenue = cash = expenses = receivables = advances = payables = balances = None
    quotes = repairs = inventory = hr = invoices = gates = None

    if finance_ok or invoice_ok:
        revenue = safe("revenue", lambda: _revenue(db, start, end))
    if cash_ok or finance_ok:
        cash = safe("cash_received", lambda: _cash_received(db, start, end))
        expenses = safe("expenses", lambda: _expenses(db, start, end))
        balances = safe("cash_bank", lambda: _cash_bank_balances(db))
    if invoice_ok or finance_ok:
        receivables = safe("receivables", lambda: _receivables(db))
        advances = safe("customer_advances", lambda: _customer_advances(db))
        invoices = safe("invoices", lambda: _invoices_list(db, start, end))
        quotes = safe("quotes", lambda: _quotes(db))
    if vendor_ok or finance_ok:
        payables = safe("supplier_payables", lambda: _supplier_payables(db))
    if repair_ok:
        repairs = safe("repairs", lambda: _repairs(db))
    if inv_ok:
        inventory = safe("inventory", lambda: _inventory(db))
    if hr_ok:
        hr = safe("hr", lambda: _hr(db))
    if car_ok:
        gates = safe("gate_passes", lambda: _gate_passes(db))

    # KPIs — order depends on view; only include what we have
    def add_kpi(*args, **kwargs):
        kpis.append(_kpi(*args, **kwargs))

    if revenue is not None:
        add_kpi(
            "Revenue (invoiced)",
            revenue["total"],
            href=f"/invoices?{qs}",
            meta=f"{revenue['count']} invoice(s) in range",
            kind="money",
        )
    if cash is not None:
        add_kpi(
            "Cash received",
            cash["total"],
            href=f"/finance/cash-received?{qs}",
            meta=f"{cash['count']} receipt(s) — not the same as revenue",
            kind="money",
        )
    if receivables is not None:
        add_kpi(
            "Receivables",
            receivables["total"],
            href="/invoices?status=unpaid",
            meta=f"{receivables['count']} unpaid / partial",
            alert=receivables["count"] > 0,
            kind="money",
        )
    if advances is not None:
        add_kpi(
            "Customer advances",
            advances["total"],
            href="/invoices",
            meta="Liability held for customers",
            kind="money",
        )
    if expenses is not None:
        add_kpi(
            "Expenses",
            expenses["period_total"],
            href=f"/finance/daily-expenses?{qs}",
            meta=f"Today Rs {expenses['today_total']:,.0f}" if expenses["today_total"] else f"{expenses['count']} entries",
            kind="money",
        )
    if payables is not None:
        add_kpi(
            "Supplier payables",
            payables["total"],
            href="/vendors",
            meta=f"{payables['count']} vendor(s) owed",
            kind="money",
        )
    if balances is not None:
        add_kpi(
            "Cash / bank position",
            balances["position"],
            href="/finance/monthly-ledger",
            meta=f"In Rs {balances['total_in']:,.0f} · Out Rs {balances['total_out']:,.0f}",
            kind="money",
        )
    if repairs is not None:
        add_kpi(
            "Active repairs",
            repairs["open_count"],
            href="/repair-orders",
            meta=f"{repairs['completed_today']} completed today",
            kind="number",
        )
        add_kpi(
            "Overdue jobs",
            repairs["overdue_count"],
            href="/repair-orders?overdue=1",
            meta=f"Open > {OVERDUE_DAYS} days",
            alert=repairs["overdue_count"] > 0,
            kind="number",
        )
        add_kpi(
            "Vehicles in workshop",
            repairs["vehicles_count"],
            href="/repair-orders",
            meta="Distinct plates on open jobs",
            kind="number",
        )
    if quotes is not None:
        add_kpi(
            "Pending estimates",
            quotes["pending_count"],
            href="/quotes/pending",
            meta=f"Rs {quotes['pending_value']:,.0f} potential",
            kind="number",
        )
    if inventory is not None:
        add_kpi(
            "Low-stock alerts",
            inventory["low_stock_count"],
            href="/inventory?low_stock=1",
            meta=f"{inventory['open_po_count']} open PO(s)",
            alert=inventory["low_stock_count"] > 0,
            kind="number",
        )
    if hr is not None:
        add_kpi(
            "Workers on site",
            hr["present_count"],
            href="/hr/attendance",
            meta=f"{hr['active_workers']} active · {hr['absent_count']} not checked in",
            kind="number",
        )
    if gates is not None:
        add_kpi(
            "Gate passes today",
            gates["today_count"],
            href="/cars?gate_pass=1",
            meta=f"In {gates['in_today']} · Out {gates['out_today']}",
            kind="number",
        )

    # Package sections for searchable lists / panels
    if receivables is not None:
        sections["receivables"] = receivables
    if advances is not None:
        sections["customer_advances"] = advances
    if cash is not None:
        sections["payments"] = cash
    if expenses is not None:
        sections["expenses"] = expenses
    if invoices is not None:
        sections["invoices"] = invoices
    if quotes is not None:
        sections["quotes"] = quotes
    if repairs is not None:
        sections["repairs"] = repairs
    if inventory is not None:
        sections["inventory"] = inventory
    if payables is not None:
        sections["supplier_payables"] = payables
    if balances is not None:
        sections["cash_bank"] = balances
    if hr is not None:
        sections["hr"] = hr
    if gates is not None:
        sections["gate_passes"] = gates
    if revenue is not None:
        sections["revenue"] = revenue

    charts = {
        "revenue_daily": (revenue or {}).get("daily") or [],
        "cash_daily": (cash or {}).get("daily") or [],
        "expenses_daily": (expenses or {}).get("daily") or [],
    }

    alerts = _alerts(
        receivables=receivables or {"count": 0, "total": 0},
        repairs=repairs or {"overdue_count": 0},
        inventory=inventory or {"low_stock_count": 0},
        quotes=quotes or {"pending_count": 0},
        payables=payables or {"count": 0, "total": 0},
        advances=advances or {"total": 0},
    )

    # Filter alerts by permission
    alert_perm = {
        "low_stock": "inventory",
        "overdue_jobs": "repair-order",
        "receivables": "invoice",
        "pending_quotes": "invoice",
        "payables": "vendors",
        "advances": "invoice",
    }
    alerts = [
        a
        for a in alerts
        if alert_perm.get(a["code"], "home") in permissions
        or alert_perm.get(a["code"]) is None
    ]

    return {
        "role": user.role,
        "view": view,
        "date_range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "period": period_key,
        },
        "kpis": kpis,
        "charts": charts,
        "sections": sections,
        "alerts": alerts,
        "quick_actions": _quick_actions(permissions, view),
        "unavailable": failed,
        "generated_at": datetime.utcnow().isoformat(),
        # Legacy-compatible keys used by older UI snippets
        "insights": {
            "sales_month": (revenue or {}).get("total", 0),
            "expenses_month": (expenses or {}).get("period_total", 0),
            "profit_month": _f((revenue or {}).get("total")) - _f((expenses or {}).get("period_total")),
            "receivables": (receivables or {}).get("total", 0),
            "cash_received": (cash or {}).get("total", 0),
            "customer_advances": (advances or {}).get("total", 0),
            "supplier_payables": (payables or {}).get("total", 0),
            "cash_position": (balances or {}).get("position", 0),
        }
        if (revenue or expenses or receivables)
        else None,
    }
