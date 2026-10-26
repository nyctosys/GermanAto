"""Linking an invoice or repair order to the customer and car it was written for.

Reuses existing Customer/Car rows — never invents duplicates when a job card opens.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.customer_vehicle import find_existing_car, normalize_phone_safe
from app.models import Car, Customer


def _clean(value):
    return (value or "").strip()


def resolve_customer(db: Session, customer_id=None, name=None, phone=None):
    if customer_id:
        found = db.get(Customer, int(customer_id))
        if found and getattr(found, "deleted_at", None) is None:
            return found

    name = _clean(name)
    phone_norm = normalize_phone_safe(phone)
    phone_raw = _clean(phone)

    if name and phone_norm:
        found = (
            db.query(Customer)
            .filter(Customer.name == name, Customer.phone == phone_norm)
            .first()
        )
        if found:
            return found

    if phone_norm or phone_raw:
        from app.customer_vehicle import find_customers_by_phone

        matches = find_customers_by_phone(db, phone_norm or phone_raw, limit=2)
        if len(matches) == 1:
            return matches[0]

    if name and name != "N/A":
        matches = db.query(Customer).filter(Customer.name == name).limit(2).all()
        if len(matches) == 1:
            return matches[0]
    return None


def resolve_car(db: Session, car_id=None, plate_no=None, vin=None, customer_id=None):
    return find_existing_car(
        db,
        car_id=int(car_id) if car_id else None,
        plate_no=plate_no,
        vin=vin,
        customer_id=int(customer_id) if customer_id else None,
    )


def adopt_orphan_car(car, customer):
    if car and customer and car.customer_id is None:
        car.customer_id = customer.id
        return True
    return False


def apply_links(db: Session, document, data):
    """Attach existing customer/car FKs; do not create new master records here."""
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
