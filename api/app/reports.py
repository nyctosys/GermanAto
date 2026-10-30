"""The numbers behind every report, worked out from the journal and the documents. The routers
only add permissions and filters; the closing pack and the dashboard call these too, so the same
figure is never calculated two ways."""

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import journal
from app.models import (
    Branch, Car, CreditNote, Customer, Invoice, InvoiceLine, Item, LabourCode, MoneyEntry, Quotation, RepairOrder, RepairOrderActivity,
    RepairOrderLine, StockMovement, User, Vendor, VendorBill, VendorPayment, Visit,
)
from app.pricing import money, totals
from app.config import local_today

Z = Decimal(0)
BUCKETS = ("0-30", "31-60", "61-90", "90+")


def bucket(days: int) -> str:
    return BUCKETS[0] if days <= 30 else BUCKETS[1] if days <= 60 else BUCKETS[2] if days <= 90 else BUCKETS[3]


def pnl(db: Session, branch: Branch, start: date, end: date) -> dict:
    """Profit and loss from the journal: revenue, cost of parts sold, expenses by category, salaries, net profit."""
    b = journal.balances(db, branch, since=start, as_of=end)
    cr = lambda code: (b.get(code, (Z, Z))[1] - b.get(code, (Z, Z))[0])  # credit-normal accounts
    dr = lambda code: (b.get(code, (Z, Z))[0] - b.get(code, (Z, Z))[1])  # debit-normal accounts
    labour, parts, other = cr("4000"), cr("4100"), cr("4900")
    revenue = labour + parts + other
    cogs = dr("5000")
    expenses = journal.category_totals(db, branch, start, end)
    other_costs = {"Salaries and wages": dr("6100"), "Freight and purchase adjustments": dr("6200"),
                   "Stock write-offs and corrections": dr("6900"), "Cash over and short": dr("6910")}
    other_costs = {k: v for k, v in other_costs.items() if v}
    total_expenses = sum(expenses.values(), Z) + sum(other_costs.values(), Z)
    return {"from": start, "to": end, "revenue": {"labour": labour, "parts": parts, "other": other, "total": revenue},
            "cost_of_parts_sold": cogs, "gross_profit": revenue - cogs, "gross_margin_pct": float((revenue - cogs) / revenue * 100) if revenue else None,
            "expenses_by_category": expenses, "other_costs": other_costs, "total_expenses": total_expenses, "net_profit": revenue - cogs - total_expenses,
            "sales_tax_collected": cr("2300")}


def cashflow(db: Session, branch: Branch, start: date, end: date) -> dict:
    moves = journal.money_movement(db, branch, start, end)
    out = {}
    for kind, code in journal.MONEY_CODE.items():
        opening_d, opening_c = journal.balances(db, branch, as_of=start - timedelta(days=1)).get(code, (Z, Z))
        a = moves[kind]
        opening = opening_d - opening_c
        out[kind] = {"opening": opening, "in": a["in"], "out": a["out"], "closing": opening + a["in"] - a["out"],
                     "in_by_source": a["in_by_source"], "out_by_source": a["out_by_source"]}
    return {"from": start, "to": end, "accounts": out,
            "opening": sum((a["opening"] for a in out.values()), Z), "in": sum((a["in"] for a in out.values()), Z),
            "out": sum((a["out"] for a in out.values()), Z), "closing": sum((a["closing"] for a in out.values()), Z)}


def receivables(db: Session, branch: Branch, as_of: date | None = None) -> dict:
    """Every issued invoice that is not settled, aged from the day it was issued. A negative balance is money owed back."""
    from app.routers.billing import balance_of
    today = as_of or local_today()
    rows, by_bucket = [], defaultdict(lambda: Z)
    names = {c.id: c.name for c in db.scalars(select(Customer).where(Customer.id.in_(select(Invoice.customer_id).where(Invoice.branch_id == branch.id))))}
    for inv in db.scalars(select(Invoice).where(Invoice.branch_id == branch.id, Invoice.status == "issued").order_by(Invoice.issued_at)):
        bal = balance_of(db, inv)["balance"]
        if bal == 0:
            continue
        days = (today - inv.issued_at.date()).days
        rows.append({"id": inv.id, "number": inv.number, "kind": inv.kind, "customer": names.get(inv.customer_id, inv.walk_in_name or "Walk-in customer"),
                     "issued_on": inv.issued_at.date(), "days": days, "bucket": bucket(days) if bal > 0 else "credit", "balance": bal})
        by_bucket[bucket(days) if bal > 0 else "credit"] += bal
    return {"as_of": today, "rows": rows, "by_bucket": dict(by_bucket), "total": sum((r["balance"] for r in rows), Z)}


def payables(db: Session, branch: Branch, as_of: date | None = None) -> dict:
    from app.routers.purchasing import bill_totals
    today = as_of or local_today()
    rows, by_bucket = [], defaultdict(lambda: Z)
    names = {v.id: v.name for v in db.scalars(select(Vendor).where(Vendor.branch_id == branch.id))}
    for b in db.scalars(select(VendorBill).where(VendorBill.branch_id == branch.id, VendorBill.status == "posted").order_by(VendorBill.due_on)):
        bal = bill_totals(db, b)["balance"]
        if bal <= 0:
            continue
        overdue = max((today - b.due_on).days, 0)
        label = "not yet due" if overdue == 0 else bucket(overdue)
        rows.append({"id": b.id, "number": b.number, "vendor": names[b.vendor_id], "due_on": b.due_on, "days_overdue": overdue, "bucket": label, "balance": bal})
        by_bucket[label] += bal
    return {"as_of": today, "rows": rows, "by_bucket": dict(by_bucket), "total": sum((r["balance"] for r in rows), Z)}


def stock_value(db: Session, branch: Branch) -> dict:
    """Quantity and value per item: the sum of its movements at the cost each moved at, so it equals the Inventory account."""
    rows = db.execute(select(Item.id, Item.number, Item.name, Item.unit, Item.reorder_level, func.sum(StockMovement.qty), func.sum(StockMovement.qty * StockMovement.unit_cost))
                      .join(StockMovement, StockMovement.item_id == Item.id).where(Item.branch_id == branch.id)
                      .group_by(Item.id, Item.number, Item.name, Item.unit, Item.reorder_level).order_by(Item.name)).all()
    items = [{"id": i, "number": n, "name": nm, "unit": u, "on_hand": q, "value": money(v), "avg_cost": money(v / q) if q else Z, "low": rl > 0 and q <= rl}
             for i, n, nm, u, rl, q, v in rows if q or v]
    return {"items": items, "total": sum((i["value"] for i in items), Z), "low_stock": sum(1 for i in items if i["low"])}


def discounts_and_voids(db: Session, branch: Branch, start: date, end: date) -> dict:
    lo, hi = datetime.combine(start, datetime.min.time()), datetime.combine(end + timedelta(days=1), datetime.min.time())
    users = {u.id: u.full_name for u in db.scalars(select(User))}
    disc = []
    for inv in db.scalars(select(Invoice).where(Invoice.branch_id == branch.id, Invoice.status == "issued", Invoice.discount > 0,
                                                Invoice.issued_at >= lo.astimezone(), Invoice.issued_at < hi.astimezone())):
        disc.append({"id": inv.id, "number": inv.number, "by": users.get(inv.issued_by), "discount": totals(inv)["discount"]})
    voids = [{"kind": "money entry", "number": m.number, "amount": m.amount, "reason": m.void_reason}
             for m in db.scalars(select(MoneyEntry).where(MoneyEntry.branch_id == branch.id, MoneyEntry.status == "voided",
                                                          MoneyEntry.occurred_on >= start, MoneyEntry.occurred_on <= end))]
    voids += [{"kind": "vendor payment", "number": p.number, "amount": p.amount, "reason": p.void_reason}
              for p in db.scalars(select(VendorPayment).where(VendorPayment.branch_id == branch.id, VendorPayment.status == "voided", VendorPayment.paid_at >= lo.astimezone(), VendorPayment.paid_at < hi.astimezone()))]
    by_user: dict = defaultdict(lambda: Z)
    for d in disc:
        by_user[d["by"] or "Unknown"] += d["discount"]
    return {"discounts": disc, "discount_total": sum((d["discount"] for d in disc), Z), "discounts_by_user": dict(by_user), "voids": voids}


# --- operations ---------------------------------------------------------------------------------------

def operations(db: Session, branch: Branch, start: date, end: date) -> dict:
    lo, hi = datetime.combine(start, datetime.min.time()).astimezone(), datetime.combine(end + timedelta(days=1), datetime.min.time()).astimezone()
    visits = db.scalars(select(Visit).where(Visit.branch_id == branch.id, Visit.checked_in_at >= lo, Visit.checked_in_at < hi)).all()
    by_status = defaultdict(int)
    for v in visits:
        by_status[v.status] += 1
    closed = [v for v in visits if v.status == "closed" and v.closed_at]
    turnaround = sum(((v.closed_at - v.checked_in_at).total_seconds() / 3600 for v in closed), 0.0) / len(closed) if closed else None

    invoices = db.scalars(select(Invoice).where(Invoice.branch_id == branch.id, Invoice.status == "issued", Invoice.issued_at >= lo, Invoice.issued_at < hi)).all()
    channel = {"workshop": Z, "counter_sale": Z}
    for inv in invoices:
        t = totals(inv)
        channel["workshop" if inv.kind == "inspection" else inv.kind] += t["subtotal"] - t["discount"]
    workshop = [i for i in invoices if i.kind in ("workshop", "inspection")]

    labour = db.execute(select(LabourCode.code, LabourCode.name, func.count(), func.sum(InvoiceLine.qty * InvoiceLine.unit_price))
                        .join(InvoiceLine, InvoiceLine.labour_code_id == LabourCode.id).join(Invoice, Invoice.id == InvoiceLine.invoice_id)
                        .where(Invoice.branch_id == branch.id, Invoice.status == "issued", Invoice.issued_at >= lo, Invoice.issued_at < hi)
                        .group_by(LabourCode.code, LabourCode.name).order_by(func.sum(InvoiceLine.qty * InvoiceLine.unit_price).desc()).limit(10)).all()
    parts = db.execute(select(Item.number, Item.name, func.sum(InvoiceLine.qty), func.sum(InvoiceLine.qty * InvoiceLine.unit_price))
                       .join(InvoiceLine, InvoiceLine.item_id == Item.id).join(Invoice, Invoice.id == InvoiceLine.invoice_id)
                       .where(Invoice.branch_id == branch.id, Invoice.status == "issued", Invoice.issued_at >= lo, Invoice.issued_at < hi)
                       .group_by(Item.number, Item.name).order_by(func.sum(InvoiceLine.qty * InvoiceLine.unit_price).desc()).limit(10)).all()

    comebacks = []
    for v in visits:
        prev = db.scalar(select(Visit).where(Visit.car_id == v.car_id, Visit.id != v.id, Visit.status == "closed", Visit.closed_at < v.checked_in_at,
                                             Visit.closed_at >= v.checked_in_at - timedelta(days=30)).order_by(Visit.closed_at.desc()))
        if prev:
            car = db.get(Car, v.car_id)
            comebacks.append({"visit_id": v.id, "number": v.number, "plate": car.plate, "previous": prev.number, "days": (v.checked_in_at - prev.closed_at).days})

    quotes = db.scalars(select(Quotation).where(Quotation.branch_id == branch.id, Quotation.status != "revised", Quotation.created_at >= lo, Quotation.created_at < hi)).all()
    sent = [q for q in quotes if q.status != "draft"]
    won = [q for q in sent if q.status in ("approved", "converted")]

    stage_seconds: dict = defaultdict(float)
    stage_count: dict = defaultdict(int)
    for ro in db.scalars(select(RepairOrder).where(RepairOrder.branch_id == branch.id, RepairOrder.created_at >= lo, RepairOrder.created_at < hi)):
        marks = db.scalars(select(RepairOrderActivity).where(RepairOrderActivity.repair_order_id == ro.id, RepairOrderActivity.kind == "status")
                           .order_by(RepairOrderActivity.created_at)).all()
        for a, b in zip(marks, marks[1:]):
            if a.to_status and a.to_status not in ("on_hold",):  # time on hold is not time in a stage
                stage_seconds[a.to_status] += (b.created_at - a.created_at).total_seconds()
                stage_count[a.to_status] += 1
    stages = {k: stage_seconds[k] / stage_count[k] / 3600 for k in stage_seconds}

    aging = defaultdict(int)
    now = datetime.now().astimezone()
    for ro in db.scalars(select(RepairOrder).where(RepairOrder.branch_id == branch.id, RepairOrder.status != "delivered")):
        days = (now - ro.created_at).days
        aging["0-2 days" if days <= 2 else "3-7 days" if days <= 7 else "8-14 days" if days <= 14 else "over 14 days"] += 1

    return {"from": start, "to": end, "visits": {"total": len(visits), "by_status": dict(by_status), "avg_turnaround_hours": turnaround},
            "revenue_by_channel": channel, "revenue_per_visit": (channel["workshop"] / len(workshop)) if workshop else None,
            "top_labour": [{"code": c, "name": n, "lines": k, "revenue": money(r)} for c, n, k, r in labour],
            "top_parts": [{"number": n, "name": nm, "qty": q, "revenue": money(r)} for n, nm, q, r in parts],
            "comebacks": comebacks, "quotations": {"made": len(quotes), "sent": len(sent), "won": len(won),
                                                   "conversion_pct": (len(won) / len(sent) * 100) if sent else None},
            "avg_hours_in_stage": stages, "open_repair_orders_by_age": dict(aging)}


# --- people --------------------------------------------------------------------------------------------

def hr_report(db: Session, branch: Branch, month: str) -> dict:
    from app import attendance
    from app.models import Employee, PayrollLine, PayrollRun
    from app.routers.payroll import outstanding
    start, end = attendance.month_range(month)
    emps = db.scalars(select(Employee).where(Employee.branch_id == branch.id, Employee.joined_on <= end).order_by(Employee.full_name)).all()
    rows, advances = [], []
    for e in emps:
        if e.left_on and e.left_on < start:
            continue
        t = attendance.summarise(db, e, start, end)
        rows.append({"employee_id": e.id, "full_name": e.full_name, "present": t.present, "late": t.late, "absent": t.absent, "leave": t.paid_leave + t.unpaid_leave,
                     "working_days": t.working_days, "hours": t.hours})
        given, recovered = outstanding(db, e.id)
        if given - recovered:
            advances.append({"employee_id": e.id, "full_name": e.full_name, "outstanding": given - recovered})
    cost = [{"month": r.month, "status": r.status, "gross": sum((l.net_pay + l.advance_recovery for l in r.lines), Z), "net": sum((l.net_pay for l in r.lines), Z)}
            for r in db.scalars(select(PayrollRun).where(PayrollRun.branch_id == branch.id, PayrollRun.status != "void").order_by(PayrollRun.month.desc()).limit(12))]
    # What each person billed: labour lines marked done on repair orders, by technician (a measure of productivity, not hours).
    prod = db.execute(select(User.full_name, func.count(), func.sum(RepairOrderLine.qty * RepairOrderLine.unit_price))
                      .join(RepairOrderLine, RepairOrderLine.technician_id == User.id).join(RepairOrder, RepairOrder.id == RepairOrderLine.repair_order_id)
                      .where(RepairOrder.branch_id == branch.id, RepairOrderLine.kind == "labour", RepairOrderLine.state == "done",
                             RepairOrder.created_at >= datetime.combine(start, datetime.min.time()).astimezone(),
                             RepairOrder.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()).astimezone())
                      .group_by(User.full_name).order_by(func.sum(RepairOrderLine.qty * RepairOrderLine.unit_price).desc())).all()
    return {"month": month, "attendance": rows, "payroll_cost": cost, "advances_outstanding": advances,
            "advances_total": sum((a["outstanding"] for a in advances), Z),
            "technicians": [{"name": n, "jobs": k, "labour_billed": money(v)} for n, k, v in prod]}
