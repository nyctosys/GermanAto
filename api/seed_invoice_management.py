"""Seed Invoice Management demo data (DB direct). Safe to re-run — skips if marker exists.

Creates customer/vehicle, job cards, ROs, invoices in unpaid / partial / paid /
credit-note states, plus one pending quote. Posts CustomerLedger accrual + cash.

Usage (from api/):
  .venv\\Scripts\\python.exe seed_invoice_management.py
  # or: python seed_invoice_management.py

Then open http://localhost:5173/invoices
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.customer_ar import (
    create_credit_note,
    post_accrual_on_finalize,
    post_deposit_application,
    post_payment_credit,
    rebuild_invoice_totals,
)
from app.db import SessionLocal
from app.document_numbers import invoice_document_no, repair_order_document_no
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.models import (
    Car,
    Customer,
    Invoice,
    InvoiceItem,
    InvoiceLabour,
    JobCard,
    RepairOrder,
)

MARKER = "SEED-INV-MGMT"
MARKER_PHONE = "03009998877"
MARKER_PLATE = "INV-SEED-01"


def _customer(db) -> Customer:
    row = (
        db.query(Customer)
        .filter(Customer.phone == MARKER_PHONE, Customer.deleted_at.is_(None))
        .first()
    )
    if row:
        return row
    row = Customer(
        name="Bilal Hussain (Invoice Demo)",
        phone=MARKER_PHONE,
        address="Model Town A-Block, Lahore",
        customer_type="retail",
        consent_whatsapp=True,
        branch_id=DEFAULT_BRANCH_ID,
        created_by_user="seed",
    )
    db.add(row)
    db.flush()
    return row


def _car(db, customer: Customer) -> Car:
    row = (
        db.query(Car)
        .filter(Car.plate_no == MARKER_PLATE, Car.deleted_at.is_(None))
        .first()
    )
    if row:
        row.customer_id = customer.id
        return row
    row = Car(
        make="Toyota",
        model="Corolla Altis 2019",
        year=2019,
        plate_no=MARKER_PLATE,
        mileage="78400",
        vin="JTDBR32E190SEED01",
        color="White",
        customer_id=customer.id,
        branch_id=DEFAULT_BRANCH_ID,
        created_by_user="seed",
    )
    db.add(row)
    db.flush()
    return row


def _job_card(db, customer: Customer, car: Car, *, notes: str) -> JobCard:
    jc = JobCard(
        customer_id=customer.id,
        car_id=car.id,
        customer_name=customer.name or "",
        customer_phone=customer.phone or "",
        customer_reg_no=car.plate_no or "",
        customer_made=f"{car.make} {car.model}",
        status="quoted",
        notes=notes,
        created_by_user="seed",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(jc)
    db.flush()
    return jc


def _ro(
    db,
    customer: Customer,
    car: Car,
    jc: JobCard,
    *,
    problem: str,
    status: str = "completed",
) -> RepairOrder:
    ro = RepairOrder(
        customer_name=customer.name or "",
        customer_phone=customer.phone or "",
        customer_address=customer.address or "",
        customer_reg_no=car.plate_no or "",
        customer_made=f"{car.make} {car.model}",
        customer_mileage=car.mileage or "",
        customer_vin=car.vin,
        customer_color=car.color,
        problem_description=problem,
        diagnosis_plan="Per approved estimate",
        current_status=status,
        customer_id=customer.id,
        car_id=car.id,
        job_card_id=jc.id,
        notes=f"{MARKER}\n{problem}",
        created_by_user="seed",
        branch_id=DEFAULT_BRANCH_ID,
        due_at=datetime.utcnow() + timedelta(days=1),
    )
    db.add(ro)
    db.flush()
    ro.document_no = repair_order_document_no(ro.id)
    return ro


def _invoice(
    db,
    customer: Customer,
    car: Car,
    *,
    ro: RepairOrder | None,
    jc: JobCard | None,
    type_of: str,
    items: list[tuple[str, int, float]],
    labours: list[tuple[str, float]],
    created_days_ago: int = 0,
    advance: float = 0.0,
    discount: float = 0.0,
    include_tax: bool = False,
    tax_amount: float = 0.0,
    locked: bool = False,
) -> Invoice:
    created = datetime.utcnow() - timedelta(days=created_days_ago)
    inv = Invoice(
        customer_name=customer.name or "",
        customer_address=customer.address or "",
        customer_phone=customer.phone or "",
        customer_reg_no=car.plate_no or "",
        customer_made=f"{car.make} {car.model}",
        customer_mileage=car.mileage or "",
        customer_vin=car.vin,
        customer_color=car.color,
        customer_id=customer.id,
        car_id=car.id,
        job_card_id=jc.id if jc else None,
        repair_order_id=ro.id if ro else None,
        balance=0,
        advance=float(advance),
        net_total=0,
        discount=float(discount),
        type_of=type_of,
        include_tax=include_tax,
        tax_amount=float(tax_amount),
        paid_amount=0.0,
        status="pending" if type_of == "quote" else "unpaid",
        created_by_user="seed",
        created_at=created,
        branch_id=DEFAULT_BRANCH_ID,
        locked_at=created if locked else None,
    )
    db.add(inv)
    db.flush()
    inv.document_no = invoice_document_no(inv.id, type_of=type_of)

    for name, qty, price in items:
        db.add(
            InvoiceItem(
                invoice_id=inv.id,
                product_name=name,
                quantity=qty,
                price=price,
                approval_status="approved",
                branch_id=DEFAULT_BRANCH_ID,
            )
        )
    for desc, price in labours:
        db.add(
            InvoiceLabour(
                invoice_id=inv.id,
                description=desc,
                price=price,
                approval_status="approved",
                branch_id=DEFAULT_BRANCH_ID,
            )
        )
    db.flush()
    db.refresh(inv)
    rebuild_invoice_totals(inv)

    if jc and not jc.quote_invoice_id:
        jc.quote_invoice_id = inv.id
    if ro and not ro.quote_invoice_id:
        ro.quote_invoice_id = inv.id
    return inv


def main() -> int:
    db = SessionLocal()
    try:
        existing = (
            db.query(Invoice)
            .filter(
                Invoice.customer_phone == MARKER_PHONE,
                Invoice.deleted_at.is_(None),
                Invoice.type_of.ilike("invoice"),
            )
            .first()
        )
        if existing:
            print(f"Already seeded (invoice {existing.document_no or existing.id}).")
            print("Open /invoices — filter phone 03009998877 or plate INV-SEED-01.")
            print("To re-seed, delete those invoices (and related ROs) first.")
            return 0

        print("Seeding invoice management demo…")
        customer = _customer(db)
        car = _car(db, customer)

        # 1) Unpaid — editable (no payment yet), accrual still posted
        jc1 = _job_card(db, customer, car, notes=f"{MARKER} unpaid oil service")
        ro1 = _ro(db, customer, car, jc1, problem="Oil & filter service")
        inv1 = _invoice(
            db,
            customer,
            car,
            ro=ro1,
            jc=jc1,
            type_of="invoice",
            items=[("Engine Oil 4L Synthetic", 1, 8500.0), ("Oil Filter", 1, 1200.0)],
            labours=[("Oil change labour", 2500.0)],
            created_days_ago=3,
            locked=False,
        )
        post_accrual_on_finalize(db, inv1, username="seed")

        # 2) Partial payment + prior advance applied
        jc2 = _job_card(db, customer, car, notes=f"{MARKER} partial brakes")
        ro2 = _ro(db, customer, car, jc2, problem="Front brake pads + fluid")
        inv2 = _invoice(
            db,
            customer,
            car,
            ro=ro2,
            jc=jc2,
            type_of="invoice",
            items=[
                ("Front Brake Pad Set", 1, 6500.0),
                ("Brake Fluid DOT4 1L", 1, 1200.0),
            ],
            labours=[("Brake pad replacement", 4500.0)],
            created_days_ago=5,
            advance=2000.0,
            locked=True,
        )
        post_accrual_on_finalize(db, inv2, username="seed")
        post_deposit_application(db, inv2, amount=2000.0, username="seed")
        inv2.paid_amount = 4000.0
        rebuild_invoice_totals(inv2)
        post_payment_credit(db, inv2, amount=4000.0, username="seed", notes="Partial cash")

        # 3) Fully paid
        jc3 = _job_card(db, customer, car, notes=f"{MARKER} paid battery")
        ro3 = _ro(db, customer, car, jc3, problem="Battery replacement")
        inv3 = _invoice(
            db,
            customer,
            car,
            ro=ro3,
            jc=jc3,
            type_of="invoice",
            items=[("Battery 55Ah", 1, 18500.0)],
            labours=[("Battery fitment", 1500.0)],
            created_days_ago=10,
            locked=True,
        )
        post_accrual_on_finalize(db, inv3, username="seed")
        due3 = float(inv3.net_total or 0)
        inv3.paid_amount = due3
        rebuild_invoice_totals(inv3)
        post_payment_credit(db, inv3, amount=due3, username="seed", notes="Full settlement")

        # 4) Credit note after partial pay
        jc4 = _job_card(db, customer, car, notes=f"{MARKER} credit note case")
        ro4 = _ro(db, customer, car, jc4, problem="Suspension bushings")
        inv4 = _invoice(
            db,
            customer,
            car,
            ro=ro4,
            jc=jc4,
            type_of="invoice",
            items=[("Control Arm Bush Kit", 1, 9800.0)],
            labours=[("Bush replacement labour", 6200.0)],
            created_days_ago=7,
            locked=True,
        )
        post_accrual_on_finalize(db, inv4, username="seed")
        inv4.paid_amount = 5000.0
        rebuild_invoice_totals(inv4)
        post_payment_credit(db, inv4, amount=5000.0, username="seed")
        create_credit_note(
            db,
            inv4,
            amount=1500.0,
            reason="Price adjustment — OEM vs aftermarket",
            username="seed",
        )

        # 5) Pending quote (convert from /quotes/pending or invoice edit)
        jc5 = _job_card(db, customer, car, notes=f"{MARKER} open quote")
        _invoice(
            db,
            customer,
            car,
            ro=None,
            jc=jc5,
            type_of="quote",
            items=[("Cabin Filter", 1, 2800.0), ("Air Filter", 1, 2200.0)],
            labours=[("Filter replacement labour", 1800.0)],
            created_days_ago=1,
            locked=False,
        )
        jc5.status = "open"

        db.commit()

        print("Done. Open /invoices and search:")
        print(f"  phone {MARKER_PHONE}  |  plate {MARKER_PLATE}")
        print("Seeded:")
        for inv in (
            db.query(Invoice)
            .filter(Invoice.customer_phone == MARKER_PHONE, Invoice.deleted_at.is_(None))
            .order_by(Invoice.id)
            .all()
        ):
            print(
                f"  {inv.document_no}  type={inv.type_of}  status={inv.status}  "
                f"due={inv.net_total:.0f}  paid={(inv.advance or 0)+(inv.paid_amount or 0):.0f}  "
                f"bal={inv.balance:.0f}  locked={'yes' if inv.locked_at else 'no'}"
            )
        print("Also: /quotes/pending for the open estimate; print any row via Print.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
