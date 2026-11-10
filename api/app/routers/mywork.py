"""My work: what is waiting for this person. Every queue is worked out from the current state of the records, never from
messages between people, so each step of a job lands in front of the next person on its own: the advisor's approved quotation
appears for whoever makes repair orders, the finished repair for whoever invoices, the paid invoice for the guard.
A queue is shown only to people holding the permission that does that work."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import reports
from app.auth import Actor, require
from app.db import get_db
from app.models import (Car, CashClose, Customer, GoodsReceipt, Invoice, JobCard, Message, PayrollRun, PeriodClose, PurchaseOrder, Punch,
                        Quotation, RepairOrder, Vendor, VendorBill, Visit)
from app.config import local_today

router = APIRouter(prefix="/api", tags=["my work"])
SHOW = 5  # items listed per queue; the rest are behind "see all"


def _car(db: Session, car_id) -> str:
    c = db.get(Car, car_id)
    return f"{c.plate} {c.make} {c.model}".strip()


def build(db: Session, actor: Actor) -> list[dict]:
    from app.routers.billing import gate_queue  # late import: billing imports this package's neighbours
    b, today, can = actor.branch, local_today(), actor.can
    groups: list[dict] = []

    def add(key: str, title: str, do: str, items: list[dict], href: str):
        if items:
            groups.append({"key": key, "title": title, "do": do, "count": len(items), "items": items[:SHOW], "href": href})

    def cust(visit_id) -> str:
        v = db.get(Visit, visit_id)
        return db.get(Customer, v.customer_id).name

    # --- the workshop, in the order a job travels ---
    if can("job-cards"):
        rows = db.execute(select(Visit).where(Visit.branch_id == b.id, Visit.status == "open", Visit.kind == "workshop",
                                              ~select(JobCard.id).where(JobCard.visit_id == Visit.id).exists(),
                                              ~select(RepairOrder.id).where(RepairOrder.visit_id == Visit.id).exists()).order_by(Visit.checked_in_at)).scalars()
        add("job-card", "Cars waiting for a job card", "Write the list of work to quote.",
            [{"label": _car(db, v.car_id), "sub": cust(v.id), "href": f"/visits/{v.id}", "since": v.checked_in_at} for v in rows], "/visits")
    if can("quotations"):
        qs = list(db.scalars(select(Quotation).where(Quotation.branch_id == b.id, Quotation.status.in_(("draft", "sent"))).order_by(Quotation.created_at)))
        add("quote-draft", "Quotations to price and send", "Price every line, then send it to the customer.",
            [{"label": q.number, "sub": cust(q.visit_id), "href": f"/quotations/{q.id}", "since": q.created_at} for q in qs if q.status == "draft"], "/quotations?status=draft")
        add("quote-wait", "Waiting for the customer's answer", "Follow up, then record the approval.",
            [{"label": q.number, "sub": f"{cust(q.visit_id)}, valid until {q.valid_until:%d %b}", "href": f"/quotations/{q.id}", "since": q.sent_at}
             for q in qs if q.status == "sent"], "/quotations?status=sent")
    if can("repair-orders"):
        qs = db.scalars(select(Quotation).where(Quotation.branch_id == b.id, Quotation.status == "approved",
                                                ~select(RepairOrder.id).where(RepairOrder.visit_id == Quotation.visit_id).exists()).order_by(Quotation.approved_at))
        add("make-ro", "Approved: make the repair order", "The customer agreed. Start the work.",
            [{"label": q.number, "sub": cust(q.visit_id), "href": f"/quotations/{q.id}", "since": q.approved_at} for q in qs], "/quotations?status=approved")
        ros = list(db.scalars(select(RepairOrder).where(RepairOrder.branch_id == b.id, RepairOrder.status.not_in(("ready", "delivered"))).order_by(RepairOrder.created_at)))
        add("repairs", "Repairs in progress", "Issue parts, mark jobs done, move the job along.",
            [{"label": f"{_car(db, db.get(Visit, r.visit_id).car_id)}", "sub": f"{r.number}, {sum(1 for l in r.lines if l.state == 'pending')} jobs to do"
              + (", on hold" if r.status == "on_hold" else ""), "href": f"/repair-orders/{r.id}", "since": r.created_at} for r in ros], "/repair-orders")
    if can("invoices"):
        ros = db.scalars(select(RepairOrder).where(RepairOrder.branch_id == b.id, RepairOrder.status == "ready",
                                                   ~select(Invoice.id).where(Invoice.visit_id == RepairOrder.visit_id, Invoice.kind == "workshop", Invoice.status != "void").exists()))
        add("make-invoice", "Finished repairs: make the invoice", "Make the invoice from the repair order.",
            [{"label": r.number, "sub": cust(r.visit_id), "href": f"/repair-orders/{r.id}", "since": r.updated_at} for r in ros], "/repair-orders?status=ready")
    if can("invoice-issue"):
        invs = db.scalars(select(Invoice).where(Invoice.branch_id == b.id, Invoice.status == "draft", Invoice.kind.in_(("workshop", "inspection"))).order_by(Invoice.created_at))
        add("issue-invoice", "Invoices to check and issue", "Check the prices, then issue it.",
            [{"label": i.number, "sub": cust(i.visit_id) if i.visit_id else "", "href": f"/invoices/{i.id}", "since": i.created_at} for i in invs], "/invoices?status=draft")
    if can("payments-in"):
        rec = reports.receivables(db, b)
        add("payment", "Waiting for payment", "Take the payment and attach proof.",
            [{"label": r["number"], "sub": f"{r['customer']}, Rs {r['balance']:,.0f} owed, {r['days']} days", "href": f"/invoices/{r['id']}"} for r in rec["rows"] if r["balance"] > 0],
            "/invoices?status=owing")
    if can("gate") or can("visits"):
        q = gate_queue(actor, db)
        add("gate", "Cars ready to leave", "Check the paperwork, then release the car with the gate pass.",
            [{"label": c["plate"], "sub": f"{c['car']}, {c['customer']}" + (f", owes Rs {c['balance']:,.0f}" if c["balance"] > 0 else ""), "href": "/gate"} for c in q], "/gate")

    # --- stock and buying ---
    if can("goods-receipt"):
        pos = db.scalars(select(PurchaseOrder).where(PurchaseOrder.branch_id == b.id, PurchaseOrder.status.in_(("sent", "partly_received"))).order_by(PurchaseOrder.created_at))
        add("deliveries", "Deliveries to receive", "Count the goods in when they arrive.",
            [{"label": p.number, "sub": db.get(Vendor, p.vendor_id).name, "href": f"/purchase-orders/{p.id}", "since": p.created_at} for p in pos], "/purchase-orders")
    if can("inventory"):
        low = [i for i in reports.stock_value(db, b)["items"] if i["low"]]
        add("low-stock", "Running low: order more", "Make a purchase order for these.",
            [{"label": i["name"], "sub": f"{i['on_hand']:g} {i['unit']} left", "href": f"/inventory/{i['id']}"} for i in low], "/inventory?stock=low")
    if can("purchasing"):
        grns = db.scalars(select(GoodsReceipt).where(GoodsReceipt.branch_id == b.id,
                                                     ~select(VendorBill.id).where(VendorBill.goods_receipt_id == GoodsReceipt.id, VendorBill.status != "void").exists()).order_by(GoodsReceipt.received_on))
        add("need-bill", "Deliveries waiting for the vendor's bill", "Record the bill from the vendor's invoice.",
            [{"label": g.number, "sub": f"{db.get(Vendor, g.vendor_id).name}, received {g.received_on:%d %b}", "href": f"/purchase-orders/{g.purchase_order_id}"} for g in grns], "/purchase-orders")

    # --- money ---
    if can("payments-out"):
        pay = reports.payables(db, b)
        due = [r for r in pay["rows"] if (r["due_on"] - today).days <= 7]
        add("pay-bills", "Vendor bills to pay", "Pay what is overdue or due this week.",
            [{"label": r["number"], "sub": f"{r['vendor']}, Rs {r['balance']:,.0f}, " + (f"{r['days_overdue']} days late" if r["days_overdue"] else f"due {r['due_on']:%d %b}"), "href": f"/bills/{r['id']}"} for r in due], "/bills")
    if can("cash-close"):
        open_accounts = [k for k in ("cash", "bank", "wallet") if not (last := db.scalar(select(func.max(CashClose.close_date)).where(CashClose.branch_id == b.id, CashClose.account == k))) or last < today]
        add("cash-close", "Close today's cash", "Count the drawer, the bank and the wallet and sign.",
            [{"label": "Cash, bank and wallet", "sub": f"Not yet counted today: {', '.join(open_accounts)}", "href": "/cash-close"}] if open_accounts else [], "/cash-close")
    if can("evidence-signoff"):
        from app.routers import moneybook
        waiting = moneybook.missing_proof_summary(db, actor)["open"]
        add("proof", "Payments with no proof", "Read the reason and accept it, or ask for the proof.",
            [{"label": f"{waiting} record{'s' if waiting != 1 else ''} waiting", "sub": "Waiting for an admin to accept them", "href": "/missing-evidence"}] if waiting else [], "/missing-evidence")
    if can("period-close"):
        from app.routers.periods import months_between
        first = db.scalar(select(func.min(Invoice.created_at)).where(Invoice.branch_id == b.id))
        closed = {p for (p,) in db.execute(select(PeriodClose.period).where(PeriodClose.branch_id == b.id, PeriodClose.kind == "month", PeriodClose.status == "closed"))}
        months = [m for m in months_between(first.date(), today)[:-1] if m not in closed] if first else []
        add("month-end", "Months to close", "Work the checklist, then close the month.",
            [{"label": datetime.strptime(m, "%Y-%m").strftime("%B %Y"), "sub": "Not closed yet", "href": f"/periods/{m}"} for m in months], "/periods")

    # --- people ---
    if can("hr"):
        n = db.scalar(select(func.count()).select_from(Punch).where(Punch.branch_id == b.id, Punch.employee_id.is_(None)))
        add("punches", "Attendance punches nobody owns", "Give each device number to its employee.",
            [{"label": f"{n} unmatched punch{'es' if n != 1 else ''}", "sub": "Fingerprint or face machine", "href": "/attendance"}] if n else [], "/attendance")
    if can("payroll"):
        runs = db.scalars(select(PayrollRun).where(PayrollRun.branch_id == b.id, PayrollRun.status.in_(("draft", "approved"))).order_by(PayrollRun.month))
        add("payroll", "Salary runs to finish", "Approve the run, then pay each person.",
            [{"label": r.number, "sub": f"{r.month}, {'to approve' if r.status == 'draft' else 'approved: pay each person'}", "href": f"/payroll/{r.id}"} for r in runs], "/payroll")
    if can("messages"):
        failed = list(db.scalars(select(Message).where(Message.branch_id == b.id, Message.status == "failed").order_by(Message.created_at.desc())))
        add("messages", "Messages that did not send", "Read the reason and try again.",
            [{"label": m.template_key.replace("_", " "), "sub": m.error[:60], "href": "/messages?status=failed"} for m in failed], "/messages?status=failed")
    return groups


@router.get("/my-work")
def my_work(actor: Actor = Depends(require("dashboard")), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    groups = build(db, actor)
    for g in groups:
        for it in g["items"]:
            s = it.get("since")
            it["waiting_hours"] = round((now - s).total_seconds() / 3600) if s else None
            it.pop("since", None)
    return {"groups": groups, "total": sum(g["count"] for g in groups)}
