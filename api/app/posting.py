"""The journal entry each business event produces (spec D3). Called from the
routes right before they commit, so a document and its books succeed or fail together."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app import journal
from app.journal import MONEY_CODE, Line, q
from app.models import Branch, CreditNote, Invoice, MoneyEntry, Payment, StockMovement, VendorBill, VendorPayment
from app.pricing import totals

Z = Decimal(0)


def stock_movement(db: Session, branch: Branch, m: StockMovement, memo: str) -> None:
    """Inventory against whatever caused the movement. Value is quantity x the cost it moved at."""
    value = q(abs(m.qty) * m.unit_cost)
    inward = m.qty > 0
    other = {"opening": "3900", "grn": "2100", "return": "5000", "credit": "5000",
             "issue": "5000", "sale": "5000", "adjustment": "6900"}[m.kind]
    journal.post(db, branch, memo, [Line("1200", debit=value) if inward else Line("1200", credit=value),
                                    Line(other, credit=value) if inward else Line(other, debit=value)],
                 source=("stock_movement", m.id))


def invoice_issued(db: Session, branch: Branch, inv: Invoice) -> None:
    """Receivable for the total; revenue split into labour and parts with the discount shared out in proportion; tax payable."""
    t = totals(inv)
    discount_labour = q(t["discount"] * t["labour"] / t["subtotal"]) if t["subtotal"] else Z
    labour, parts = t["labour"] - discount_labour, t["parts"] - (t["discount"] - discount_labour)
    journal.post(db, branch, f"Invoice {inv.number} issued",
                 [Line("1100", debit=t["total"]), Line("4000", credit=labour), Line("4100", credit=parts), Line("2300", credit=t["tax"])],
                 on=inv.issued_at.date(), source=("invoice", inv.id))


def credit_note(db: Session, branch: Branch, cn: CreditNote) -> None:
    """Reverses the credited share of the invoice: revenue and tax out, receivable down."""
    t = totals(cn)
    discount_labour = q(t["discount"] * t["labour"] / t["subtotal"]) if t["subtotal"] else Z
    labour, parts = t["labour"] - discount_labour, t["parts"] - (t["discount"] - discount_labour)
    journal.post(db, branch, f"Credit note {cn.number}",
                 [Line("4000", debit=labour), Line("4100", debit=parts), Line("2300", debit=t["tax"]), Line("1100", credit=t["total"])],
                 source=("credit_note", cn.id))


def advances_applied(db: Session, branch: Branch, inv: Invoice, advances: list[Payment]) -> None:
    """The customer's advance stops being a liability and settles the receivable."""
    total = sum((p.held for p in advances), Z)
    journal.post(db, branch, f"Advances applied to {inv.number}", [Line("2200", debit=total), Line("1100", credit=total)],
                 source=("invoice_advances", inv.id))


def customer_payment(db: Session, branch: Branch, p: Payment) -> None:
    """Money in: an advance is held for the customer, an invoice payment settles the receivable."""
    held = "2200" if p.kind == "advance" else "1100"
    journal.post(db, branch, f"Payment {p.number}", [Line(MONEY_CODE[p.account], debit=p.amount), Line(held, credit=p.amount)],
                 on=p.received_at.date(), source=("payment", p.id))


def vendor_bill(db: Session, branch: Branch, b: VendorBill) -> None:
    """What we owe: the goods received become a payable; freight (+) or a discount (-) goes to purchase adjustments."""
    total = b.goods_value + b.adjustment
    journal.post(db, branch, f"Bill {b.number}",
                 [Line("2100", debit=b.goods_value), Line("6200", debit=b.adjustment) if b.adjustment > 0 else Line("6200", credit=-b.adjustment),
                  Line("2000", credit=total)], on=b.bill_date, source=("vendor_bill", b.id))


def vendor_payment(db: Session, branch: Branch, p: VendorPayment) -> None:
    journal.post(db, branch, f"Vendor payment {p.number}", [Line("2000", debit=p.amount), Line(MONEY_CODE[p.account], credit=p.amount)],
                 on=p.paid_at.date(), source=("vendor_payment", p.id))


def money_entry(db: Session, branch: Branch, e: MoneyEntry) -> None:
    """Other income, owner capital, an expense (by category), owner drawings, or a transfer between accounts."""
    here = MONEY_CODE[e.account]
    lines = {
        "other_income": [Line(here, debit=e.amount), Line("4900", credit=e.amount)],
        "owner_capital": [Line(here, debit=e.amount), Line("3000", credit=e.amount)],
        "expense": [Line("6000", debit=e.amount, category_id=e.category_id), Line(here, credit=e.amount)],
        "drawings": [Line("3100", debit=e.amount), Line(here, credit=e.amount)],
        "transfer": [Line(MONEY_CODE[e.to_account or "cash"], debit=e.amount), Line(here, credit=e.amount)],
        # A refund gives back money we held (an advance) or money the customer overpaid (after a credit note).
        "refund": [Line("2200" if e.payment_id else "1100", debit=e.amount), Line(here, credit=e.amount)],
        "salary_advance": [Line("1300", debit=e.amount), Line(here, credit=e.amount)],   # money lent to an employee, to be recovered from pay
        "salary": [Line("2400", debit=e.amount), Line(here, credit=e.amount)],            # paying off the salaries payable
    }[e.kind]
    journal.post(db, branch, f"{e.number}" + (f": {e.party}" if e.party else ""), lines, on=e.occurred_on, source=("money_entry", e.id))


def cash_difference(db: Session, branch: Branch, kind: str, difference: Decimal, on: date, source_id) -> None:
    """Brings the books to what was counted: a shortage is an expense, a surplus is income to this account."""
    code = MONEY_CODE[kind]
    journal.post(db, branch, f"Cash count difference ({kind})",
                 [Line("6910", debit=-difference), Line(code, credit=-difference)] if difference < 0
                 else [Line(code, debit=difference), Line("6910", credit=difference)], on=on, source=("cash_close", source_id))


def payroll_approved(db: Session, branch: Branch, run, lines) -> None:
    """The month's salary expense, with advances recovered out of it and the rest owed to staff until paid."""
    gross = sum((l.net_pay + l.advance_recovery for l in lines), Z)
    recovery = sum((l.advance_recovery for l in lines), Z)
    net = sum((l.net_pay for l in lines), Z)
    journal.post(db, branch, f"Payroll {run.number} for {run.month}",
                 [Line("6100", debit=gross), Line("1300", credit=recovery), Line("2400", credit=net)], source=("payroll_run", run.id))


def void_source(db: Session, branch: Branch, source_type: str, source_id, memo: str, on: date | None = None) -> None:
    """Reverses the live entry for a document that was voided."""
    entry = journal.live_entry(db, source_type, source_id)
    if entry:
        journal.reverse(db, branch, entry, memo, on=on)
