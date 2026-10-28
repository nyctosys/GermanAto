"""Money arithmetic shared by quotations, invoices and the journal: one place decides how totals round."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(v: Decimal) -> Decimal:
    return v.quantize(CENT, ROUND_HALF_UP)


def totals(q) -> dict:
    """For a quotation or an invoice: lines (declined ones drop out), discount, tax."""
    lines = [l for l in q.lines if not getattr(l, "declined", False)]
    labour = sum((money(l.qty * l.unit_price) for l in lines if l.kind == "labour"), Decimal(0))
    parts = sum((money(l.qty * l.unit_price) for l in lines if l.kind == "part"), Decimal(0))
    subtotal = labour + parts
    discount = min(q.discount, subtotal)
    tax = money((subtotal - discount) * q.tax_rate / 100) if q.include_tax else Decimal(0)
    return {"labour": labour, "parts": parts, "subtotal": subtotal, "discount": discount, "tax": tax,
            "total": subtotal - discount + tax}
