"""Seed Vendor / PO / GRN / invoice / payment demo data (DB direct).

Safe to re-run — skips if marker vendor "SEED-PROC-AUTO" exists.

Usage (from api/):
  .venv\\Scripts\\python.exe seed_procurement.py
  # or: python seed_procurement.py

Then open http://localhost:5173/vendors and click into each seeded vendor.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from app.db import Base, SessionLocal, engine
from app.document_numbers import assign_document_numbers
from app.foundation.branch import DEFAULT_BRANCH_ID, ensure_default_branch
from app.models import Inventory, PurchaseOrder, Vendor
from app.procurement import (
    create_supplier_invoice,
    post_credit_note,
    receive_goods,
    record_supplier_payment,
)

MARKER_VENDOR = "SEED-PROC-AUTO"
MARKER_VENDOR_B = "SEED-PROC-PARTS"
MARKER_VENDOR_C = "SEED-PROC-OVERDUE"


def _money(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


def _get_or_create_part(
    db,
    *,
    part_number: str,
    name: str,
    category: str,
    qty: int,
    avg_cost: float,
    price: float,
    unit: str = "pcs",
    reorder_level: int = 5,
    preferred_vendor_id: int | None = None,
) -> Inventory:
    row = db.query(Inventory).filter_by(part_number=part_number).first()
    if row:
        if preferred_vendor_id and not row.preferred_vendor_id:
            row.preferred_vendor_id = preferred_vendor_id
        return row
    row = Inventory(
        part_number=part_number,
        name=name,
        category=category,
        quantity=qty,
        reserved=0,
        avg_cost=_money(avg_cost),
        price=float(price),
        unit=unit,
        pack_size=1,
        reorder_level=reorder_level,
        min_level=reorder_level,
        reorder_quantity=max(10, reorder_level * 2),
        preferred_vendor_id=preferred_vendor_id,
        barcode=f"SEED{part_number[-6:]}",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(row)
    db.flush()
    return row


def _vendor(
    db,
    *,
    name: str,
    company: str,
    phone: str,
    contact: str,
    terms: int = 30,
    address: str = "Industrial Area, Lahore",
) -> Vendor:
    row = (
        db.query(Vendor)
        .filter(Vendor.name == name, Vendor.phone == phone)
        .first()
    )
    if row:
        return row
    row = Vendor(
        name=name,
        company_name=company,
        contact_person=contact,
        phone=phone,
        email=f"{phone[-7:]}@parts.example",
        address=address,
        cnic=None,
        payment_terms_days=terms,
        bank_details="HBL · PK12 HABB 0000 1234 5678 9012",
        notes="Seeded procurement demo vendor",
        branch_id=DEFAULT_BRANCH_ID,
        created_by_user="seed",
    )
    db.add(row)
    db.flush()
    return row


def _po(
    db,
    *,
    vendor: Vendor,
    item: Inventory,
    qty: int,
    rate: float,
    status: str,
    expected_in: int | None = 7,
    remarks: str | None = None,
) -> PurchaseOrder:
    today = date.today()
    po = PurchaseOrder(
        vendor_id=vendor.id,
        inventory_id=item.id,
        date=today - timedelta(days=2),
        expected_delivery=(today + timedelta(days=expected_in)) if expected_in is not None else None,
        invoice_no=f"PO-SEED-{vendor.id}-{item.id}-{status[:3].upper()}",
        item_name=item.name,
        unit=item.unit or "pcs",
        quantity=qty,
        qty_received=0,
        rate=_money(rate),
        amount=_money(rate) * qty,
        remarks=remarks or "Seed PO",
        status=status,
        branch_id=DEFAULT_BRANCH_ID,
        created_by_user="seed",
    )
    if status in ("approved", "ordered", "partial", "received"):
        po.approved_at = datetime.utcnow() - timedelta(days=1)
        po.approved_by_user = "seed"
    db.add(po)
    db.flush()
    return po


def main() -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_branch(db)

        existing = db.query(Vendor).filter(Vendor.name == MARKER_VENDOR).first()
        if existing:
            print(f"Already seeded (vendor '{MARKER_VENDOR}' id={existing.id}).")
            print("Open /vendors in the web app to explore.")
            print("To re-seed, delete that vendor (and related rows) first.")
            return 0

        print("Seeding procurement demo…")

        # --- Vendors ---
        auto = _vendor(
            db,
            name=MARKER_VENDOR,
            company="AutoParts Hub (Pvt) Ltd",
            phone="03001110001",
            contact="Imran Qureshi",
            terms=30,
        )
        parts_co = _vendor(
            db,
            name=MARKER_VENDOR_B,
            company="Lahore Filters & Friction",
            phone="03002220002",
            contact="Nadia Raza",
            terms=15,
        )
        overdue_v = _vendor(
            db,
            name=MARKER_VENDOR_C,
            company="Karachi Lubricants Wholesale",
            phone="03003330003",
            contact="Farooq Ali",
            terms=7,
            address="SITE Area, Karachi",
        )
        assign_document_numbers(db)
        db.flush()
        print(f"  vendors: {auto.code}, {parts_co.code}, {overdue_v.code}")

        # --- Catalogue ---
        oil_filter = _get_or_create_part(
            db,
            part_number="SEED-OF-001",
            name="Oil Filter (seed)",
            category="Filters",
            qty=4,
            avg_cost=420,
            price=850,
            reorder_level=8,
            preferred_vendor_id=parts_co.id,
        )
        brake_pad = _get_or_create_part(
            db,
            part_number="SEED-BP-002",
            name="Brake Pad Set Front (seed)",
            category="Brakes",
            qty=2,
            avg_cost=3200,
            price=4500,
            unit="set",
            reorder_level=4,
            preferred_vendor_id=auto.id,
        )
        engine_oil = _get_or_create_part(
            db,
            part_number="SEED-EO-003",
            name="Engine Oil 4L Synthetic (seed)",
            category="Lubricants",
            qty=1,
            avg_cost=4800,
            price=6200,
            unit="bottle",
            reorder_level=6,
            preferred_vendor_id=overdue_v.id,
        )
        air_filter = _get_or_create_part(
            db,
            part_number="SEED-AF-004",
            name="Air Filter Cabin (seed)",
            category="Filters",
            qty=12,
            avg_cost=900,
            price=1500,
            preferred_vendor_id=parts_co.id,
        )
        print("  inventory parts ready")

        # --- PO lifecycle on AutoParts Hub ---
        # 1) Draft — staff can Approve
        draft_po = _po(
            db,
            vendor=auto,
            item=brake_pad,
            qty=6,
            rate=3100,
            status="draft",
            expected_in=5,
            remarks="Seed: waiting approval",
        )
        # 2) Approved — staff can Order
        approved_po = _po(
            db,
            vendor=auto,
            item=air_filter,
            qty=10,
            rate=880,
            status="approved",
            expected_in=3,
            remarks="Seed: approved, place order",
        )
        # 3) Ordered — ready to receive (leave untouched for manual Receive)
        ordered_po = _po(
            db,
            vendor=auto,
            item=brake_pad,
            qty=4,
            rate=3150,
            status="ordered",
            expected_in=2,
            remarks="Seed: try Receive on this row",
        )
        # 4) Partial receive already done + invoice + partial payment
        partial_po = _po(
            db,
            vendor=auto,
            item=oil_filter,
            qty=20,
            rate=400,
            status="ordered",
            expected_in=0,
            remarks="Seed: partially received",
        )
        assign_document_numbers(db)
        db.flush()

        grn1, _ = receive_goods(
            db,
            po=partial_po,
            qty=8,
            unit_cost=400,
            item=oil_filter,
            verified_qty=8,
            receipt_path="uploads/seed-grn-partial-oil.pdf",
            notes="Seed partial GRN",
            username="seed",
        )
        inv1 = create_supplier_invoice(
            db,
            vendor=auto,
            amount=float(grn1.amount),
            supplier_invoice_no="SI-SEED-OF-001",
            invoice_date=date.today() - timedelta(days=1),
            goods_receipt=grn1,
            purchase_order=partial_po,
            notes="Seed invoice for partial GRN",
            username="seed",
        )
        record_supplier_payment(
            db,
            vendor=auto,
            amount=1500,
            payment_date=date.today(),
            method="bank",
            reference="CHQ-SEED-1001",
            supplier_invoice=inv1,
            notes="Seed partial payment",
            username="seed",
        )
        print(f"  AutoParts: draft #{draft_po.id}, approved #{approved_po.id}, "
              f"ordered #{ordered_po.id}, partial PO #{partial_po.id} + invoice + payment")

        # --- Filters vendor: full receive → invoice → paid + a credit note example ---
        full_po = _po(
            db,
            vendor=parts_co,
            item=air_filter,
            qty=5,
            rate=900,
            status="ordered",
            expected_in=-1,
            remarks="Seed: fully received & paid",
        )
        assign_document_numbers(db)
        db.flush()
        grn2, _ = receive_goods(
            db,
            po=full_po,
            qty=5,
            unit_cost=900,
            item=air_filter,
            verified_qty=5,
            receipt_path="uploads/seed-grn-full-air.pdf",
            notes="Seed full GRN",
            username="seed",
        )
        inv2 = create_supplier_invoice(
            db,
            vendor=parts_co,
            amount=float(grn2.amount),
            supplier_invoice_no="SI-SEED-AF-100",
            invoice_date=date.today() - timedelta(days=5),
            goods_receipt=grn2,
            purchase_order=full_po,
            username="seed",
        )
        record_supplier_payment(
            db,
            vendor=parts_co,
            amount=float(inv2.amount),
            payment_date=date.today() - timedelta(days=1),
            method="cash",
            reference="CASH-SEED-88",
            supplier_invoice=inv2,
            username="seed",
        )

        # Return 1 unit with credit + small cash refund
        return_po = _po(
            db,
            vendor=parts_co,
            item=oil_filter,
            qty=3,
            rate=410,
            status="ordered",
            remarks="Seed: return demo",
        )
        assign_document_numbers(db)
        db.flush()
        grn3, _ = receive_goods(
            db,
            po=return_po,
            qty=3,
            unit_cost=410,
            item=oil_filter,
            verified_qty=3,
            receipt_path="uploads/seed-grn-return-src.pdf",
            username="seed",
        )
        inv3 = create_supplier_invoice(
            db,
            vendor=parts_co,
            amount=float(grn3.amount),
            supplier_invoice_no="SI-SEED-RET-01",
            goods_receipt=grn3,
            purchase_order=return_po,
            username="seed",
        )
        note = post_credit_note(
            db,
            vendor=parts_co,
            amount=410,
            reason="Damaged seal — seed return",
            quantity=1,
            unit_cost=410,
            refund_amount=0,
            purchase_order=return_po,
            goods_receipt=grn3,
            supplier_invoice=inv3,
            item=oil_filter,
            username="seed",
        )
        print(f"  Filters co: paid cycle + credit note {note.document_no}")

        # --- Overdue vendor: open invoice past due (shows on Reports → Overdue) ---
        overdue_po = _po(
            db,
            vendor=overdue_v,
            item=engine_oil,
            qty=12,
            rate=4700,
            status="ordered",
            expected_in=-10,
            remarks="Seed: overdue payable",
        )
        assign_document_numbers(db)
        db.flush()
        grn4, _ = receive_goods(
            db,
            po=overdue_po,
            qty=12,
            unit_cost=4700,
            item=engine_oil,
            verified_qty=12,
            receipt_path="uploads/seed-grn-overdue-oil.pdf",
            username="seed",
        )
        overdue_inv = create_supplier_invoice(
            db,
            vendor=overdue_v,
            amount=float(grn4.amount),
            supplier_invoice_no="SI-SEED-OVERDUE-01",
            invoice_date=date.today() - timedelta(days=20),
            due_date=date.today() - timedelta(days=10),
            goods_receipt=grn4,
            purchase_order=overdue_po,
            notes="Seed overdue — appears on overdue payables report",
            username="seed",
        )
        print(f"  Overdue invoice {overdue_inv.document_no} due {overdue_inv.due_date}")

        # Low-stock hint: leave engine oil / brake low so Inventory reorder suggestions show
        assign_document_numbers(db)
        db.commit()

        print()
        print("Done. Try in the UI:")
        print(f"  1. /vendors → open '{MARKER_VENDOR}'")
        print("     · Purchase orders: Approve draft, Order approved, Receive ordered")
        print("     · Goods receipts: invoice remaining GRN qty on partial PO")
        print("     · Invoices & payments / Ledger / Export statement")
        print(f"  2. /vendors → '{MARKER_VENDOR_B}' for paid + credit-note history")
        print(f"  3. /vendors → '{MARKER_VENDOR_C}' for outstanding balance")
        print("  4. /reports → Overdue payables")
        print("  5. /inventory → Reorder suggestions (seed parts below min)")
        return 0
    except Exception as exc:
        db.rollback()
        print("Seed failed:", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
