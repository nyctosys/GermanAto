"""Linking an invoice or repair order to the customer and car it was written for."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Car, Customer


def _clean(value):
    return (value or "").strip()


def resolve_customer(db: Session, customer_id=None, name=None, phone=None):
    if customer_id:
        found = db.get(Customer, int(customer_id))
        if found:
            return found

    name, phone = _clean(name), _clean(phone)

    if name and phone:
        found = db.query(Customer).filter(Customer.name == name, Customer.phone == phone).first()
        if found:
            return found
    if phone:
        matches = db.query(Customer).filter(Customer.phone == phone).limit(2).all()
        if len(matches) == 1:
            return matches[0]
    if name:
        matches = db.query(Customer).filter(Customer.name == name).limit(2).all()
        if len(matches) == 1:
            return matches[0]
    return None


def resolve_car(db: Session, car_id=None, plate_no=None, vin=None, customer_id=None):
    if car_id:
        found = db.get(Car, int(car_id))
        if found:
            return found

    plate_no, vin = _clean(plate_no), _clean(vin)

    for column, value in ((Car.vin, vin), (Car.plate_no, plate_no)):
        if not value:
            continue
        query = db.query(Car).filter(column == value)
        if customer_id:
            owned = query.filter(Car.customer_id == customer_id).first()
            if owned:
                return owned
        matches = query.limit(2).all()
        if len(matches) == 1:
            return matches[0]
    return None


def adopt_orphan_car(car, customer):
    if car and customer and car.customer_id is None:
        car.customer_id = customer.id
        return True
    return False


def apply_links(db: Session, document, data):
    customer = resolve_customer(
        db,
        data.get("customer_id"),
        data.get("customer_name"),
        data.get("customer_phone"),
    )
    car = resolve_car(
        db,
        data.get("car_id"),
        data.get("customer_reg_no"),
        data.get("customer_vin"),
        customer.id if customer else None,
    )

    document.customer_id = customer.id if customer else None
    document.car_id = car.id if car else None
    adopt_orphan_car(car, customer)
    return customer, car
