"""Seed demo Repair Execution data (DB direct). Safe to re-run — skips if marker RO exists.

Usage (from api/):
  .venv\\Scripts\\python.exe seed_repair_execution.py
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.db import SessionLocal
from app.document_numbers import assign_document_numbers
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.models import (
    Car,
    Customer,
    Inventory,
    LabourCode,
    RepairFault,
    RepairOrder,
    RepairOrderLabour,
    RepairOrderPart,
    RepairTimeEntry,
    Variation,
    VariationLine,
    Worker,
)
from app.repair_execution import _recalc_ro_costs


MARKER = "SEED-REX-COROLLA"


def _get_or_create_customer(db) -> Customer:
    row = (
        db.query(Customer)
        .filter(Customer.phone == "03005551234", Customer.deleted_at.is_(None))
        .first()
    )
    if row:
        return row
    row = Customer(
        name="Sara Malik",
        phone="03005551234",
        address="DHA Phase 5, Lahore",
        customer_type="retail",
        consent_whatsapp=True,
        branch_id=DEFAULT_BRANCH_ID,
        created_by_user="seed",
    )
    db.add(row)
    db.flush()
    return row


def _get_or_create_car(db, customer: Customer) -> Car:
    row = (
        db.query(Car)
        .filter(Car.plate_no == "LES-8842", Car.deleted_at.is_(None))
        .first()
    )
    if row:
        row.customer_id = customer.id
        return row
    row = Car(
        make="Honda",
        model="Civic 2020",
        year=2020,
        plate_no="LES-8842",
        mileage="61200",
        vin="JHMEG1234LS012345",
        color="Silver",
        customer_id=customer.id,
        branch_id=DEFAULT_BRANCH_ID,
        created_by_user="seed",
    )
    db.add(row)
    db.flush()
    return row


def _get_or_create_worker(db) -> Worker:
    row = db.query(Worker).filter(Worker.employee_id == "TECH-01").first()
    if row:
        return row
    row = Worker(
        employee_id="TECH-01",
        first_name="Usman",
        last_name="Ali",
        phone="03331234567",
        address="Township, Lahore",
        cnic="3520211111111",
        date_of_birth=date(1994, 3, 15),
        hire_date=date(2023, 6, 1),
        position="Technician",
        department="Workshop",
        salary=Decimal("48000.00"),
        status="active",
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(row)
    db.flush()
    return row


def _labour_code(db, code: str, desc: str, hours: float, rate: float) -> LabourCode:
    row = db.query(LabourCode).filter(LabourCode.code == code).first()
    if row:
        return row
    row = LabourCode(
        code=code,
        description=desc,
        standard_hours=hours,
        rate=rate,
        category="general",
        is_active=True,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(row)
    db.flush()
    return row


def _inventory(
    db, *, name: str, category: str, qty: int, price: float, cost: float, barcode: str
) -> Inventory:
    row = db.query(Inventory).filter(Inventory.barcode == barcode).first()
    if row:
        row.quantity = max(int(row.quantity or 0), qty)
        row.avg_cost = Decimal(str(cost))
        row.price = price
        return row
    row = Inventory(
        name=name,
        category=category,
        quantity=qty,
        reserved=0,
        price=price,
        avg_cost=Decimal(str(cost)),
        barcode=barcode,
        reorder_level=3,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(row)
    db.flush()
    return row


def run() -> int:
    db = SessionLocal()
    try:
        existing = (
            db.query(RepairOrder)
            .filter(RepairOrder.notes.contains(MARKER), RepairOrder.deleted_at.is_(None))
            .first()
        )
        if existing:
            print(f"Seed already present: RO #{existing.id} — open /repair-orders/{existing.id}/execution")
            print("  Also try /repair-execution for the technician board.")
            return 0

        customer = _get_or_create_customer(db)
        car = _get_or_create_car(db, customer)
        worker = _get_or_create_worker(db)
        assign_document_numbers(db)

        lc_brake = _labour_code(db, "BRK-PAD", "Brake pad replacement", 1.5, 2500.0)
        lc_diag = _labour_code(db, "DIAG-01", "Road test + diagnosis", 0.5, 1800.0)
        lc_ac = _labour_code(db, "AC-REGAS", "A/C performance check", 1.0, 2200.0)

        pads = _inventory(
            db,
            name="Front Brake Pad Set Civic",
            category="Brakes",
            qty=12,
            price=6500,
            cost=4200,
            barcode="SEED-PAD-001",
        )
        fluid = _inventory(
            db,
            name="Brake Fluid DOT4 1L",
            category="Fluids",
            qty=20,
            price=1200,
            cost=700,
            barcode="SEED-FLD-001",
        )
        filter_ = _inventory(
            db,
            name="Cabin Filter Honda",
            category="Filters",
            qty=15,
            price=2800,
            cost=1600,
            barcode="SEED-FLT-001",
        )

        due = datetime.utcnow() + timedelta(days=2)
        workers_json = json.dumps([{"id": worker.id, "name": f"{worker.first_name} {worker.last_name}"}])

        ro = RepairOrder(
            customer_name=customer.name or "Sara Malik",
            customer_phone=customer.phone or "03005551234",
            customer_address=customer.address or "",
            customer_reg_no=car.plate_no or "LES-8842",
            customer_made=f"{car.make} {car.model}",
            customer_mileage=car.mileage or "61200",
            customer_vin=car.vin,
            customer_color=car.color,
            problem_description="Front brakes squealing; soft pedal after mountain drive",
            diagnosis_plan="Replace front pads, flush fluid, road test",
            worker_id=worker.id,
            worker_name=f"{worker.first_name} {worker.last_name}",
            workers_json=workers_json,
            current_status="in_progress",
            customer_id=customer.id,
            car_id=car.id,
            notes=f"{MARKER}\nDemo RO for Repair Execution workbench.",
            due_at=due,
            created_by_user="seed",
            branch_id=DEFAULT_BRANCH_ID,
        )
        db.add(ro)
        db.flush()

        # Labour: one done-ish, one in progress (clockable), one pending
        lab_done = RepairOrderLabour(
            repair_order_id=ro.id,
            description=lc_diag.description,
            status="done",
            labour_code_id=lc_diag.id,
            approval_status="approved",
            assigned_worker_id=worker.id,
            std_hours=lc_diag.standard_hours,
            actual_hours=0.6,
            labour_rate=lc_diag.rate,
            labour_cost=round(0.6 * lc_diag.rate, 2),
            started_at=datetime.utcnow() - timedelta(hours=3),
            completed_at=datetime.utcnow() - timedelta(hours=2),
            deadline_at=due,
            line_notes="Noise confirmed on left front.",
            branch_id=DEFAULT_BRANCH_ID,
        )
        lab_active = RepairOrderLabour(
            repair_order_id=ro.id,
            description=lc_brake.description,
            status="paused",
            labour_code_id=lc_brake.id,
            approval_status="approved",
            assigned_worker_id=worker.id,
            std_hours=lc_brake.standard_hours,
            actual_hours=0.75,
            labour_rate=lc_brake.rate,
            labour_cost=round(0.75 * lc_brake.rate, 2),
            started_at=datetime.utcnow() - timedelta(hours=2),
            paused_at=datetime.utcnow() - timedelta(minutes=20),
            deadline_at=due,
            line_notes="Pads removed; waiting on fluid top-up.",
            branch_id=DEFAULT_BRANCH_ID,
        )
        lab_pending = RepairOrderLabour(
            repair_order_id=ro.id,
            description=lc_ac.description,
            status="Approved",
            labour_code_id=lc_ac.id,
            approval_status="approved",
            assigned_worker_id=worker.id,
            std_hours=lc_ac.standard_hours,
            actual_hours=0.0,
            labour_rate=lc_ac.rate,
            labour_cost=0.0,
            deadline_at=due + timedelta(days=1),
            branch_id=DEFAULT_BRANCH_ID,
        )
        db.add_all([lab_done, lab_active, lab_pending])
        db.flush()

        db.add(
            RepairTimeEntry(
                repair_order_id=ro.id,
                labour_id=lab_done.id,
                worker_id=worker.id,
                started_at=lab_done.started_at,
                ended_at=lab_done.completed_at,
                status="closed",
                hours=0.6,
                notes="Diagnosis complete",
                created_by_user="seed",
                branch_id=DEFAULT_BRANCH_ID,
            )
        )
        db.add(
            RepairTimeEntry(
                repair_order_id=ro.id,
                labour_id=lab_active.id,
                worker_id=worker.id,
                started_at=lab_active.started_at,
                ended_at=lab_active.paused_at,
                status="closed",
                hours=0.75,
                notes="Paused for parts",
                created_by_user="seed",
                branch_id=DEFAULT_BRANCH_ID,
            )
        )

        # Parts: one fully issued, one partial, one requested
        part_issued = RepairOrderPart(
            repair_order_id=ro.id,
            inventory_id=pads.id,
            description=pads.name,
            part_number=pads.part_number,
            quantity=1,
            status="issued",
            qty_issued=1,
            qty_returned=0,
            ownership_type="shop_stock",
            approval_status="approved",
            unit_cost=float(pads.avg_cost),
            branch_id=DEFAULT_BRANCH_ID,
        )
        # Deduct stock to match issued qty
        pads.quantity = max(0, int(pads.quantity or 0) - 1)

        part_partial = RepairOrderPart(
            repair_order_id=ro.id,
            inventory_id=fluid.id,
            description=fluid.name,
            part_number=fluid.part_number,
            quantity=2,
            status="partial",
            qty_issued=1,
            qty_returned=0,
            ownership_type="shop_stock",
            approval_status="approved",
            unit_cost=float(fluid.avg_cost),
            branch_id=DEFAULT_BRANCH_ID,
        )
        fluid.quantity = max(0, int(fluid.quantity or 0) - 1)

        part_req = RepairOrderPart(
            repair_order_id=ro.id,
            inventory_id=filter_.id,
            description=filter_.name,
            part_number=filter_.part_number,
            quantity=1,
            status="requested",
            qty_issued=0,
            qty_returned=0,
            ownership_type="shop_stock",
            approval_status="approved",
            unit_cost=float(filter_.avg_cost),
            branch_id=DEFAULT_BRANCH_ID,
        )
        db.add_all([part_issued, part_partial, part_req])
        db.flush()

        # Additional fault awaiting customer approval (variation draft)
        var = Variation(
            repair_order_id=ro.id,
            status="draft",
            flagged_by="seed",
            notes="Additional fault: rear caliper sticking",
            branch_id=DEFAULT_BRANCH_ID,
        )
        db.add(var)
        db.flush()
        db.add(
            VariationLine(
                variation_id=var.id,
                line_type="labour",
                description="Rear caliper service",
                labour_code_id=lc_brake.id,
                quantity=1,
                unit_price=3500,
                approval_status="pending",
                branch_id=DEFAULT_BRANCH_ID,
            )
        )
        db.add(
            RepairFault(
                repair_order_id=ro.id,
                description="Rear left caliper sticking — needs strip & clean (customer approval required)",
                severity="high",
                status="awaiting_approval",
                variation_id=var.id,
                recorded_by="seed",
                branch_id=DEFAULT_BRANCH_ID,
            )
        )

        # Second lighter RO so the board has more than one card
        ro2 = RepairOrder(
            customer_name="Bilal Ahmed",
            customer_phone="03219876543",
            customer_address="Johar Town, Lahore",
            customer_reg_no="LEB-2201",
            customer_made="Toyota Yaris 2019",
            customer_mileage="44100",
            problem_description="A/C not cooling",
            diagnosis_plan="Pressure test + regas if approved",
            worker_id=worker.id,
            worker_name=f"{worker.first_name} {worker.last_name}",
            workers_json=workers_json,
            current_status="received",
            notes=f"{MARKER}-2\nSecond demo job.",
            due_at=datetime.utcnow() + timedelta(days=4),
            created_by_user="seed",
            branch_id=DEFAULT_BRANCH_ID,
        )
        db.add(ro2)
        db.flush()
        db.add(
            RepairOrderLabour(
                repair_order_id=ro2.id,
                description=lc_ac.description,
                status="Approved",
                labour_code_id=lc_ac.id,
                approval_status="approved",
                assigned_worker_id=worker.id,
                std_hours=lc_ac.standard_hours,
                labour_rate=lc_ac.rate,
                deadline_at=ro2.due_at,
                branch_id=DEFAULT_BRANCH_ID,
            )
        )

        db.flush()
        _recalc_ro_costs(db, ro)
        _recalc_ro_costs(db, ro2)
        assign_document_numbers(db)
        db.commit()

        print("Seeded Repair Execution demo:")
        print(f"  RO #{ro.id}  {ro.customer_made} {ro.customer_reg_no}  status={ro.current_status}")
        print(f"     workbench → http://localhost:5173/repair-orders/{ro.id}/execution")
        print(f"  RO #{ro2.id} {ro2.customer_made} {ro2.customer_reg_no}  status={ro2.current_status}")
        print("  Board     → http://localhost:5173/repair-execution")
        print("  List      → http://localhost:5173/repair-orders")
        return 0
    except Exception as exc:
        db.rollback()
        print("Seed failed:", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(run())
