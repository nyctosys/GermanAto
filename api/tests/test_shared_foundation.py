"""Shared data foundation: document numbers and entity helpers."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.document_numbers import (
    assign_document_numbers,
    car_code,
    customer_code,
    invoice_document_no,
    repair_order_document_no,
    vendor_code,
)
from app.models import Car, Customer, Invoice, RepairOrder, Vendor
from app.routers import entities as entities_router


def test_document_number_formats():
    assert customer_code(1) == "CN001"
    assert customer_code(42) == "CN042"
    assert car_code(7) == "VH007"
    assert vendor_code(3) == "VN003"
    assert invoice_document_no(12, type_of="invoice") == "INV-00012"
    assert invoice_document_no(12, type_of="quote") == "QT-00012"
    assert repair_order_document_no(9) == "RO-00009"


def test_assign_document_numbers_persists_codes():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        c = Customer(name="Ali", phone="+923001234567")
        db.add(c)
        db.flush()
        assign_document_numbers(db)
        assert c.code == customer_code(c.id)

        car = Car(make="Toyota", model="Corolla", plate_no="ABC-123", customer_id=c.id)
        db.add(car)
        db.flush()
        assign_document_numbers(db)
        assert car.code == car_code(car.id)

        v = Vendor(
            name="Parts Co",
            company_name="Parts Co",
            contact_person="X",
            phone="03001234567",
            address="Lahore",
        )
        db.add(v)
        db.flush()
        assign_document_numbers(db)
        assert v.code == vendor_code(v.id)

        inv = Invoice(
            customer_name="Ali",
            customer_address="x",
            customer_phone="1",
            customer_reg_no="ABC",
            customer_made="Toyota",
            customer_mileage="1",
            balance=0,
            advance=0,
            net_total=0,
            type_of="invoice",
        )
        db.add(inv)
        db.flush()
        assign_document_numbers(db)
        assert inv.document_no == invoice_document_no(inv.id)

        ro = RepairOrder(
            customer_name="Ali",
            customer_phone="1",
            customer_address="x",
            customer_reg_no="ABC",
            customer_made="Toyota",
            customer_mileage="1",
        )
        db.add(ro)
        db.flush()
        assign_document_numbers(db)
        assert ro.document_no == repair_order_document_no(ro.id)
        db.commit()
        # Reload to prove codes persisted
        assert db.get(Customer, c.id).code == customer_code(c.id)
        assert db.get(Invoice, inv.id).document_no == invoice_document_no(inv.id)


def test_entity_search_and_customer_bundle():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        c = Customer(name="Sara Khan", phone="+923001112233", address="Lahore", code="CN001")
        db.add(c)
        db.flush()
        car = Car(
            code="VH001",
            make="Honda",
            model="City",
            plate_no="LEH-101",
            customer_id=c.id,
        )
        db.add(car)
        db.commit()

        hits = entities_router._search_customers(db, "Sara", 10)
        assert len(hits) == 1
        assert hits[0]["id"] == c.id
        assert "Sara" in hits[0]["label"]

        cars = entities_router._search_cars(db, "LEH", 10, customer_id=c.id)
        assert len(cars) == 1
        assert cars[0]["plate_no"] == "LEH-101"
        assert cars[0]["customer_id"] == c.id


def test_duplicate_customer_phone_detected():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        c = Customer(name="Sara", phone="+923111111111", code="CN001")
        db.add(c)
        db.commit()

        class User:
            username = "admin"
            role = "admin"

        resp = entities_router.check_duplicate(
            db=db,
            body={"type": "customer", "phone": "+923111111111"},
            current_user=User(),
        )
        import json

        body = json.loads(bytes(resp.body))
        assert body["duplicate"] is True
        assert body["matches"][0]["id"] == c.id
        assert any("already exists" in w for w in body["warnings"])
