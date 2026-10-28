"""Posts journal entries for documents that exist but have none, for databases that
predate posting. Safe to run again: anything already posted is skipped.

    uv run python -m app.backfill_journal
"""

from sqlalchemy import select

from app import journal, posting
from app.db import SessionLocal
from app.models import Account, Branch, Invoice, JournalEntry, Payment, StockMovement, VendorBill, VendorPayment


def posted(db, source_type, source_id) -> bool:
    return db.scalar(select(JournalEntry.id).where(JournalEntry.source_type == source_type, JournalEntry.source_id == source_id)) is not None


def run() -> dict:
    counts = {"opening": 0, "stock": 0, "invoices": 0, "advances_applied": 0, "payments": 0, "bills": 0, "vendor_payments": 0}
    with SessionLocal() as db:
        for branch in db.scalars(select(Branch)):
            journal.ensure_chart(db, branch)
            for a in db.scalars(select(Account).where(Account.branch_id == branch.id)):
                if a.opening_balance > 0 and not posted(db, "account_opening", a.id):
                    journal.sync_opening(db, branch, a); counts["opening"] += 1
            for m in db.scalars(select(StockMovement).where(StockMovement.branch_id == branch.id).order_by(StockMovement.created_at)):
                if not posted(db, "stock_movement", m.id):
                    posting.stock_movement(db, branch, m, m.reason or f"Stock {m.kind}"); counts["stock"] += 1
            for inv in db.scalars(select(Invoice).where(Invoice.branch_id == branch.id, Invoice.status == "issued")):
                if not posted(db, "invoice", inv.id):
                    posting.invoice_issued(db, branch, inv); counts["invoices"] += 1
                applied = list(db.scalars(select(Payment).where(Payment.invoice_id == inv.id, Payment.kind == "advance", Payment.status == "posted")))
                if applied and not posted(db, "invoice_advances", inv.id):
                    posting.advances_applied(db, branch, inv, applied); counts["advances_applied"] += 1
            for p in db.scalars(select(Payment).where(Payment.branch_id == branch.id, Payment.status == "posted")):
                if not posted(db, "payment", p.id):
                    posting.customer_payment(db, branch, p); counts["payments"] += 1
            for b in db.scalars(select(VendorBill).where(VendorBill.branch_id == branch.id, VendorBill.status == "posted")):
                if not posted(db, "vendor_bill", b.id):
                    posting.vendor_bill(db, branch, b); counts["bills"] += 1
            for p in db.scalars(select(VendorPayment).where(VendorPayment.branch_id == branch.id, VendorPayment.status == "posted")):
                if not posted(db, "vendor_payment", p.id):
                    posting.vendor_payment(db, branch, p); counts["vendor_payments"] += 1
        db.commit()
    return counts


if __name__ == "__main__":
    print(run())
