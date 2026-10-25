"""What an invoice is worth, what has been paid, and what that makes it.

Pure arithmetic over an Invoice - no request, no session, no HTTP. It lives on
its own because four different places need it: creating and editing invoices,
recording a payment, taking cash against an invoice, and reporting receivables.
Before this, the sums were written out by hand in each of them and drifted:
receivables ignored `advance` entirely and overstated what customers owed by
every deposit ever taken.

Anything that needs to know about invoice money should import from here rather
than from a routes module.
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
    """The status the amounts imply.

    Quotes are always 'pending' - they are not owed yet, so payment has no
    meaning for them.
    """
    if invoice.type_of.lower() == 'quote':
        return 'pending'

    total_due = invoice_amount_due(invoice)
    total_paid = invoice_amount_paid(invoice)

    if total_paid <= 0:
        return 'unpaid'
    if total_paid >= total_due or invoice.balance <= 0:
        return 'paid'
    return 'partially_paid'
