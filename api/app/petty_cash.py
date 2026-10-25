"""What belongs in the daily petty-cash till."""
from app.models import CashReceived, Expense

TILL_CATEGORIES = (
    "Fuel",
    "Maintenance",
    "Utilities",
    "Office Supplies",
    "Transportation",
    "Other",
)

TILL_SCOPE = "till"


def wants_till(args):
    """True when the caller asked for the petty-cash view."""
    return args.get("scope") == TILL_SCOPE


def till_expenses(query):
    """Expenses that are genuinely petty cash."""
    return query.filter(Expense.category.in_(TILL_CATEGORIES))


def till_receipts(query):
    """Receipts that are not settling a customer invoice."""
    return query.filter(CashReceived.invoice_id.is_(None))
