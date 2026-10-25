"""Linking an invoice or repair order to the customer and car it was written for.

Both documents store the customer and vehicle as text, and that part is right:
a document records what was true the day it was written. An invoice from March
must keep March's mileage and March's address even after the customer moves
house and drives another 8,000 km.

What was missing is *who* it was for. Without an id, "show me this customer's
cars" had to match on names that get retyped, abbreviated and misspelled -
'MR ZAIN CHUDARY SB' will not find 'Zain Chaudhry' - and a car added while no
customer was selected was simply orphaned, invisible from the customer forever.

So the text stays exactly as it is, and these ids sit alongside it.
"""
from models import db, Car, Customer


def _clean(value):
    return (value or '').strip()


def resolve_customer(customer_id=None, name=None, phone=None):
    """The customer a document belongs to.

    An explicit id always wins - it is what the user actually picked. The
    fallbacks exist for documents written before the id column, and for the
    invoice form's free-text path.
    """
    if customer_id:
        found = db.session.get(Customer, int(customer_id))
        if found:
            return found

    name, phone = _clean(name), _clean(phone)

    # Name and phone together is the only match specific enough to trust
    # outright; a shared family phone or a common name is not.
    if name and phone:
        found = Customer.query.filter(Customer.name == name, Customer.phone == phone).first()
        if found:
            return found
    if phone:
        matches = Customer.query.filter(Customer.phone == phone).limit(2).all()
        if len(matches) == 1:
            return matches[0]
    if name:
        matches = Customer.query.filter(Customer.name == name).limit(2).all()
        if len(matches) == 1:
            return matches[0]
    return None


def resolve_car(car_id=None, plate_no=None, vin=None, customer_id=None):
    """The car a document was written against.

    VIN before plate: a plate can be transferred between vehicles, a VIN cannot.
    """
    if car_id:
        found = db.session.get(Car, int(car_id))
        if found:
            return found

    plate_no, vin = _clean(plate_no), _clean(vin)

    for column, value in ((Car.vin, vin), (Car.plate_no, plate_no)):
        if not value:
            continue
        query = Car.query.filter(column == value)
        # Prefer this customer's car when two share a plate - which happens,
        # because plates get retyped as much as names do.
        if customer_id:
            owned = query.filter(Car.customer_id == customer_id).first()
            if owned:
                return owned
        matches = query.limit(2).all()
        if len(matches) == 1:
            return matches[0]
    return None


def adopt_orphan_car(car, customer):
    """A document naming both a customer and a car asserts the car is theirs.

    This is what stops the orphans accumulating: a car added before a customer
    was picked gets claimed the moment it appears on that customer's document.
    Only ever fills a blank - it never reassigns a car that already has an
    owner, because that would be a guess about someone else's records.
    """
    if car and customer and car.customer_id is None:
        car.customer_id = customer.id
        return True
    return False


def apply_links(document, data):
    """Set customer_id / car_id on a document being created or saved.

    Returns (customer, car) so the caller can log or report what was linked.
    """
    customer = resolve_customer(
        data.get('customer_id'),
        data.get('customer_name'),
        data.get('customer_phone'),
    )
    car = resolve_car(
        data.get('car_id'),
        data.get('customer_reg_no'),
        data.get('customer_vin'),
        customer.id if customer else None,
    )

    document.customer_id = customer.id if customer else None
    document.car_id = car.id if car else None
    adopt_orphan_car(car, customer)
    return customer, car
