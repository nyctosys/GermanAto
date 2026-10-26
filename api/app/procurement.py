"""Vendor AP workflow: PO → GRN → supplier invoice → payment / credit note.

Separation rules:
  - PurchaseOrder = commitment only (no stock, no payable)
  - GoodsReceipt = stock increase (+ avg_cost); no payable
  - SupplierInvoice = creates VendorLedger debit (payable)
  - SupplierPayment = VendorLedger credit (reduces payable; not a repurchase)
  - SupplierCreditNote = return stock + ledger credit (and optional cash refund)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    GoodsReceipt,
    Inventory,
    PurchaseOrder,
    SupplierCreditNote,
    SupplierInvoice,
    SupplierPayment,
    Vendor,
    VendorLedger,
)
from app.stock import (
    StockError,
    _money,
    create_vendor_payable_for_grn,
    po_receive,
    refresh_po_status,
    return_to_vendor,
)


class ProcurementError(ValueError):
    pass


def _doc(prefix: str, entity_id: int) -> str:
    return f"{prefix}-{int(entity_id):05d}"


def last_supplier_rate(
    db: Session, *, vendor_id: int, inventory_id: int | None
) -> Decimal | None:
    """Known supplier price from last PO for this vendor+item."""
    q = db.query(PurchaseOrder).filter(PurchaseOrder.vendor_id == vendor_id)
    if inventory_id:
        q = q.filter(PurchaseOrder.inventory_id == inventory_id)
    po = q.order_by(PurchaseOrder.id.desc()).first()
    if po and po.rate is not None:
        return _money(po.rate)
    return None


def known_rate_for_item(
    db: Session, *, vendor_id: int, item: Inventory | None
) -> Decimal:
    if item is None:
        return Decimal("0.00")
    last = last_supplier_rate(db, vendor_id=vendor_id, inventory_id=item.id)
    if last is not None and last > 0:
        return last
    return _money(getattr(item, "avg_cost", 0) or 0)


def vendor_outstanding(db: Session, vendor_id: int) -> Decimal:
    last = (
        db.query(VendorLedger)
        .filter_by(vendor_id=vendor_id)
        .order_by(VendorLedger.date.desc(), VendorLedger.id.desc())
        .first()
    )
    return _money(last.balance) if last else Decimal("0.00")


def post_ledger(
    db: Session,
    *,
    vendor_id: int,
    entry_date: date,
    description: str,
    debit: Decimal | float = 0,
    credit: Decimal | float = 0,
    folio: str | None = None,
    username: str | None = None,
    attachment_path: str | None = None,
    payment_notes: str | None = None,
    supplier_invoice_id: int | None = None,
    supplier_payment_id: int | None = None,
    supplier_credit_note_id: int | None = None,
    goods_receipt_id: int | None = None,
) -> VendorLedger:
    debit_m = _money(debit)
    credit_m = _money(credit)
    last_balance = vendor_outstanding(db, vendor_id)
    entry = VendorLedger(
        vendor_id=vendor_id,
        date=entry_date,
        description=description,
        folio=folio,
        debit=debit_m,
        credit=credit_m,
        balance=last_balance + debit_m - credit_m,
        created_by_user=username,
        attachment_path=attachment_path,
        payment_notes=payment_notes,
        supplier_invoice_id=supplier_invoice_id,
        supplier_payment_id=supplier_payment_id,
        supplier_credit_note_id=supplier_credit_note_id,
        goods_receipt_id=goods_receipt_id,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.flush()
    return entry


def receive_goods(
    db: Session,
    *,
    po: PurchaseOrder,
    qty: int,
    unit_cost: Decimal | float,
    item: Inventory,
    verified_qty: int | None = None,
    receipt_path: str | None = None,
    notes: str | None = None,
    username: str | None = None,
    user_id: int | None = None,
) -> tuple[GoodsReceipt, object]:
    """Stock GRN only — no payable."""
    if (po.status or "").lower() in ("draft", "closed"):
        raise ProcurementError(f"Cannot receive PO in status {po.status}")
    remaining = int(po.quantity or 0) - int(po.qty_received or 0)
    if remaining <= 0:
        raise ProcurementError("PO already fully received")
    if qty <= 0:
        raise ProcurementError("quantity must be positive")
    if qty > remaining:
        raise ProcurementError(f"quantity {qty} exceeds remaining {remaining}")
    verified = int(verified_qty if verified_qty is not None else qty)
    if verified != qty:
        raise ProcurementError(
            f"verified_qty ({verified}) must match received quantity ({qty})"
        )
    # Receipt evidence is optional — workshop often receives before paperwork arrives.

    cost = _money(unit_cost)
    try:
        txn = po_receive(
            db,
            item=item,
            qty=qty,
            unit_cost=cost,
            purchase_order=po,
            created_by=user_id,
            evidence_path=receipt_path,
            notes=notes,
        )
    except StockError as exc:
        raise ProcurementError(str(exc)) from exc

    po.inventory_id = item.id
    po.qty_received = int(po.qty_received or 0) + qty
    po.receipt_attachment_path = receipt_path
    refresh_po_status(po)
    po.updated_at = datetime.utcnow()

    amount = _money(cost * qty)
    grn = GoodsReceipt(
        purchase_order_id=po.id,
        vendor_id=po.vendor_id,
        inventory_id=item.id,
        inventory_transaction_id=txn.id,
        date=date.today(),
        quantity=qty,
        verified_qty=verified,
        unit_cost=cost,
        amount=amount,
        receipt_attachment_path=receipt_path,
        status="received",
        notes=notes,
        created_by_user=username,
    )
    db.add(grn)
    db.flush()
    grn.document_no = _doc("GRN", grn.id)
    db.flush()
    return grn, txn


def create_supplier_invoice(
    db: Session,
    *,
    vendor: Vendor,
    amount: Decimal | float,
    supplier_invoice_no: str,
    invoice_date: date | None = None,
    due_date: date | None = None,
    purchase_order: PurchaseOrder | None = None,
    goods_receipt: GoodsReceipt | None = None,
    notes: str | None = None,
    attachment_path: str | None = None,
    username: str | None = None,
) -> SupplierInvoice:
    """Create payable from supplier invoice (not from PO alone)."""
    amt = _money(amount)
    if amt <= 0:
        raise ProcurementError("invoice amount must be positive")
    if goods_receipt and goods_receipt.supplier_invoice_id:
        raise ProcurementError("Goods receipt already invoiced")
    inv_date = invoice_date or date.today()
    terms = int(getattr(vendor, "payment_terms_days", None) or 30)
    due = due_date or (inv_date + timedelta(days=terms))

    inv = SupplierInvoice(
        vendor_id=vendor.id,
        purchase_order_id=purchase_order.id if purchase_order else (
            goods_receipt.purchase_order_id if goods_receipt else None
        ),
        goods_receipt_id=goods_receipt.id if goods_receipt else None,
        supplier_invoice_no=supplier_invoice_no.strip(),
        date=inv_date,
        due_date=due,
        amount=amt,
        amount_paid=Decimal("0.00"),
        status="open",
        notes=notes,
        attachment_path=attachment_path,
        created_by_user=username,
    )
    db.add(inv)
    db.flush()
    inv.document_no = _doc("SINV", inv.id)

    ledger = post_ledger(
        db,
        vendor_id=vendor.id,
        entry_date=inv_date,
        description=f"Supplier invoice {inv.supplier_invoice_no}"
        + (f" (GRN {goods_receipt.document_no})" if goods_receipt else ""),
        debit=amt,
        folio=inv.supplier_invoice_no,
        username=username,
        attachment_path=attachment_path,
        supplier_invoice_id=inv.id,
        goods_receipt_id=goods_receipt.id if goods_receipt else None,
    )
    inv.vendor_ledger_id = ledger.id
    if goods_receipt:
        goods_receipt.supplier_invoice_id = inv.id
        goods_receipt.status = "invoiced"
    db.flush()
    return inv


def record_supplier_payment(
    db: Session,
    *,
    vendor: Vendor,
    amount: Decimal | float,
    payment_date: date | None = None,
    method: str | None = None,
    reference: str | None = None,
    supplier_invoice: SupplierInvoice | None = None,
    notes: str | None = None,
    attachment_path: str | None = None,
    username: str | None = None,
) -> SupplierPayment:
    amt = _money(amount)
    if amt <= 0:
        raise ProcurementError("payment amount must be positive")
    if supplier_invoice:
        due = _money(supplier_invoice.amount) - _money(supplier_invoice.amount_paid or 0)
        if amt > due + Decimal("0.01"):
            raise ProcurementError(f"payment {amt} exceeds invoice due {due}")

    pay = SupplierPayment(
        vendor_id=vendor.id,
        supplier_invoice_id=supplier_invoice.id if supplier_invoice else None,
        date=payment_date or date.today(),
        amount=amt,
        method=(method or "cash").strip().lower(),
        reference=reference,
        notes=notes,
        attachment_path=attachment_path,
        created_by_user=username,
    )
    db.add(pay)
    db.flush()
    pay.document_no = _doc("SPAY", pay.id)

    ledger = post_ledger(
        db,
        vendor_id=vendor.id,
        entry_date=pay.date,
        description=f"Supplier payment {pay.document_no}"
        + (f" vs {supplier_invoice.supplier_invoice_no}" if supplier_invoice else ""),
        credit=amt,
        folio=reference or pay.document_no,
        username=username,
        attachment_path=attachment_path,
        payment_notes=notes,
        supplier_invoice_id=supplier_invoice.id if supplier_invoice else None,
        supplier_payment_id=pay.id,
    )
    pay.vendor_ledger_id = ledger.id

    if supplier_invoice:
        supplier_invoice.amount_paid = _money(supplier_invoice.amount_paid or 0) + amt
        paid = _money(supplier_invoice.amount_paid)
        total = _money(supplier_invoice.amount)
        if paid >= total:
            supplier_invoice.status = "paid"
            supplier_invoice.amount_paid = total
        else:
            supplier_invoice.status = "partial"
    db.flush()
    return pay


def post_credit_note(
    db: Session,
    *,
    vendor: Vendor,
    amount: Decimal | float,
    reason: str,
    quantity: int = 0,
    unit_cost: Decimal | float = 0,
    refund_amount: Decimal | float = 0,
    purchase_order: PurchaseOrder | None = None,
    goods_receipt: GoodsReceipt | None = None,
    supplier_invoice: SupplierInvoice | None = None,
    item: Inventory | None = None,
    notes: str | None = None,
    username: str | None = None,
    user_id: int | None = None,
) -> SupplierCreditNote:
    """Return / credit: optional stock out + ledger credit (+ optional cash refund)."""
    if not (reason or "").strip():
        raise ProcurementError("reason is required")
    amt = _money(amount)
    if amt <= 0:
        raise ProcurementError("credit amount must be positive")
    qty = int(quantity or 0)
    cost = _money(unit_cost)
    refund = _money(refund_amount)

    txn = None
    inv_item = item
    if qty > 0:
        if inv_item is None and goods_receipt is not None:
            inv_item = db.get(Inventory, goods_receipt.inventory_id)
        if inv_item is None:
            raise ProcurementError("inventory item required to return stock")
        try:
            txn = return_to_vendor(
                db,
                item=inv_item,
                qty=qty,
                reason=reason,
                purchase_order=purchase_order,
                created_by=user_id,
                notes=notes,
            )
        except StockError as exc:
            raise ProcurementError(str(exc)) from exc
        if goods_receipt:
            goods_receipt.status = "returned"
        if purchase_order:
            purchase_order.qty_received = max(
                0, int(purchase_order.qty_received or 0) - qty
            )
            refresh_po_status(purchase_order)

    note = SupplierCreditNote(
        vendor_id=vendor.id,
        purchase_order_id=purchase_order.id if purchase_order else None,
        goods_receipt_id=goods_receipt.id if goods_receipt else None,
        supplier_invoice_id=supplier_invoice.id if supplier_invoice else None,
        inventory_id=inv_item.id if inv_item else None,
        inventory_transaction_id=txn.id if txn else None,
        date=date.today(),
        quantity=qty,
        unit_cost=cost,
        amount=amt,
        refund_amount=refund,
        reason=reason.strip(),
        status="posted",
        notes=notes,
        created_by_user=username,
    )
    db.add(note)
    db.flush()
    note.document_no = _doc("SCN", note.id)

    ledger = post_ledger(
        db,
        vendor_id=vendor.id,
        entry_date=note.date,
        description=f"Credit note {note.document_no}: {reason}",
        credit=amt,
        folio=note.document_no,
        username=username,
        supplier_credit_note_id=note.id,
        supplier_invoice_id=supplier_invoice.id if supplier_invoice else None,
        goods_receipt_id=goods_receipt.id if goods_receipt else None,
        payment_notes=f"Refund cash/bank {refund}" if refund > 0 else None,
    )
    note.vendor_ledger_id = ledger.id

    if supplier_invoice and amt > 0:
        # Reduce open payable on linked invoice without creating a second purchase
        remaining = _money(supplier_invoice.amount) - _money(supplier_invoice.amount_paid or 0)
        applied = min(amt, remaining)
        supplier_invoice.amount_paid = _money(supplier_invoice.amount_paid or 0) + applied
        paid = _money(supplier_invoice.amount_paid)
        total = _money(supplier_invoice.amount)
        if paid >= total:
            supplier_invoice.status = "paid"
        elif paid > 0:
            supplier_invoice.status = "partial"
    db.flush()
    return note


def overdue_payables(db: Session, *, as_of: date | None = None) -> list[dict]:
    today = as_of or date.today()
    rows = (
        db.query(SupplierInvoice, Vendor)
        .join(Vendor, Vendor.id == SupplierInvoice.vendor_id)
        .filter(SupplierInvoice.status.in_(("open", "partial")))
        .filter(SupplierInvoice.due_date.isnot(None))
        .filter(SupplierInvoice.due_date < today)
        .order_by(SupplierInvoice.due_date.asc())
        .all()
    )
    out = []
    for inv, vendor in rows:
        due_amt = float(_money(inv.amount) - _money(inv.amount_paid or 0))
        if due_amt <= 0:
            continue
        out.append(
            {
                **inv.to_dict(),
                "vendor_name": vendor.name,
                "vendor_code": vendor.code,
                "company_name": vendor.company_name,
                "days_overdue": (today - inv.due_date).days if inv.due_date else 0,
            }
        )
    return out


# Keep create_vendor_payable_for_grn import available for legacy callers / tests.
__all__ = [
    "ProcurementError",
    "receive_goods",
    "create_supplier_invoice",
    "record_supplier_payment",
    "post_credit_note",
    "overdue_payables",
    "known_rate_for_item",
    "last_supplier_rate",
    "vendor_outstanding",
    "post_ledger",
    "create_vendor_payable_for_grn",
]
