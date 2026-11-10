"""Money arithmetic shared by quotations, invoices and the journal: one place decides how totals round."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
RUPEE = Decimal("1")


def money(v: Decimal) -> Decimal:
    return v.quantize(CENT, ROUND_HALF_UP)


def rupees(v: Decimal) -> Decimal:
    """Settle a document total in whole rupees (half rounds up), so the amount people see is payable."""
    return v.quantize(RUPEE, ROUND_HALF_UP)


def totals(q) -> dict:
    """For a quotation or an invoice: lines (declined ones drop out), discount, tax.

    Tax is on the lines before the discount, so a rupee off the bill does not take a rupee
    off sales tax. Line amounts keep paisa; the final total (and tax with it) rounds to
    whole rupees so a cashier can pay the figure on screen without a half-rupee mismatch.
    """
    lines = [l for l in q.lines if not getattr(l, "declined", False)]
    labour = sum((money(l.qty * l.unit_price) for l in lines if l.kind == "labour"), Decimal(0))
    parts = sum((money(l.qty * l.unit_price) for l in lines if l.kind == "part"), Decimal(0))
    subtotal = labour + parts
    discount = min(q.discount, subtotal)
    net = subtotal - discount
    if q.include_tax:
        total = rupees(net + money(subtotal * q.tax_rate / 100))
        tax = total - net
    else:
        tax = Decimal(0)
        total = rupees(net)
    return {"labour": labour, "parts": parts, "subtotal": subtotal, "discount": discount, "tax": tax,
            "total": total}
