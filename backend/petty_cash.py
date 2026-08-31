"""What belongs in the daily petty-cash till.

Daily Expenses is a till: small cash in, small cash out, and a balance that
should read as roughly what is in the drawer. Three kinds of money were
drowning that.

  * Customer invoice settlements. `cash_received` holds Rs 50.8M of them
    against a few thousand rupees of genuine daily takings, so the
    "Cash - Expenses" balance meant nothing at all.
  * Parts bought from vendors. Keyed in here by hand *and* recorded against
    the vendor in the vendor ledger, so every parts purchase was counted twice.
  * Payroll and capital spending, which each have their own page.

None of it is hidden. Reports, the monthly ledger and every export still count
all of it exactly as before - this narrowing applies only where a caller asks
for it with `scope=till`, which is the Daily Expenses page and nothing else.

One limitation worth knowing: receipts taken before `cash_received.invoice_id`
existed all have it NULL, so widening the date range on that page back past
2026-08-31 will show historical settlements among the petty cash. Those 765
rows carry no invoice reference to recover - see
migrate_cash_received_invoice_link.py.
"""
from models import CashReceived, Expense

# Expense categories whose money is owned by another ledger.
LEDGER_OWNED_CATEGORIES = ('Parts', 'Labor', 'Major Expenses')

# Callers opt in with this, so nothing else changes shape by accident.
TILL_SCOPE = 'till'


def wants_till(args):
    """True when the caller asked for the petty-cash view."""
    return args.get('scope') == TILL_SCOPE


def till_expenses(query):
    """Expenses that are genuinely petty cash."""
    return query.filter(~Expense.category.in_(LEDGER_OWNED_CATEGORIES))


def till_receipts(query):
    """Receipts that are not settling a customer invoice."""
    return query.filter(CashReceived.invoice_id.is_(None))
