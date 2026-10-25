"""What an invoice is worth, what has been paid, and what that makes it.

Pure arithmetic over an Invoice - no request, no session, no HTTP.
"""


def invoice_amount_due(invoice):
    """What the customer owes in total: net total plus tax, less any discount."""
    total = invoice.net_total
    if invoice.include_tax and invoice.tax_amount:
        total += invoice.tax_amount
    return total - (invoice.discount or 0.0)


def invoice_amount_paid(invoice):
    """Everything received so far, taken as advance or as later payments."""
    return (invoice.advance or 0.0) + (invoice.paid_amount or 0.0)


def invoice_amount_remaining(invoice):
    """Still owed, rounded to whole paisa to keep float noise out of comparisons."""
    return round(invoice_amount_due(invoice) - invoice_amount_paid(invoice), 2)


def calculate_invoice_status(invoice):
    """The status the amounts imply. Quotes are always 'pending'."""
    if invoice.type_of.lower() == "quote":
        return "pending"

    total_due = invoice_amount_due(invoice)
    total_paid = invoice_amount_paid(invoice)

    if total_paid <= 0:
        return "unpaid"
    if total_paid >= total_due or invoice.balance <= 0:
        return "paid"
    return "partially_paid"
