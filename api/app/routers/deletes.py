"""Deleting records made by mistake.

One rule everywhere: a record is removed for good only when nothing else points to it. If it has been used (stock moved,
a visit, a bill, a payslip...) the database refuses, and the person is told to mark it inactive instead. Money and stock
records are never deleted here; they are voided or reversed so the history stays."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Actor, require
from app.db import get_db
from app.models import (Attachment, Car, CarOwnership, Customer, Employee, Item, ItemVendor, LabourCode, PurchaseOrder, Quotation, Vendor)

router = APIRouter(prefix="/api", tags=["delete"])


def _remove(db: Session, obj, what: str, also: tuple = ()) -> dict:
    """Delete `obj` (and `also`, rows that only exist for it) unless another record still uses it."""
    try:
        for x in also:
            db.delete(x)
        db.flush()
        db.delete(obj)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"This {what} is already used in other records, so it can't be deleted. Mark it inactive instead.")
    for a in db.scalars(select(Attachment).where(Attachment.entity_id == obj.id)):
        a.entity_type, a.entity_id = None, None
    db.commit()
    return {"ok": True}


def _own(db: Session, actor: Actor, model, id_: uuid.UUID, label: str):
    obj = db.get(model, id_)
    if not obj or (hasattr(model, "branch_id") and obj.branch_id != actor.branch.id):
        raise HTTPException(404, f"{label} not found")
    return obj


@router.delete("/items/{item_id}")
def delete_item(item_id: uuid.UUID, actor: Actor = Depends(require("inventory")), db: Session = Depends(get_db)):
    item = _own(db, actor, Item, item_id, "Item")
    links = tuple(db.scalars(select(ItemVendor).where(ItemVendor.item_id == item.id)))
    return _remove(db, item, "item", links)


@router.delete("/labour-codes/{code_id}")
def delete_labour_code(code_id: uuid.UUID, actor: Actor = Depends(require("labour-codes")), db: Session = Depends(get_db)):
    return _remove(db, _own(db, actor, LabourCode, code_id, "Labour code"), "labour code")


@router.delete("/vendors/{vendor_id}")
def delete_vendor(vendor_id: uuid.UUID, actor: Actor = Depends(require("vendors")), db: Session = Depends(get_db)):
    vendor = _own(db, actor, Vendor, vendor_id, "Vendor")
    links = tuple(db.scalars(select(ItemVendor).where(ItemVendor.vendor_id == vendor.id)))
    return _remove(db, vendor, "vendor", links)


@router.delete("/employees/{employee_id}")
def delete_employee(employee_id: uuid.UUID, actor: Actor = Depends(require("hr")), db: Session = Depends(get_db)):
    return _remove(db, _own(db, actor, Employee, employee_id, "Employee"), "employee")


@router.delete("/customers/{customer_id}")
def delete_customer(customer_id: uuid.UUID, actor: Actor = Depends(require("customers")), db: Session = Depends(get_db)):
    customer = _own(db, actor, Customer, customer_id, "Customer")
    if db.scalar(select(CarOwnership.id).where(CarOwnership.customer_id == customer.id)):
        raise HTTPException(409, "This customer has cars on record. Delete the cars first, or mark the customer inactive.")
    return _remove(db, customer, "customer")


@router.delete("/cars/{car_id}")
def delete_car(car_id: uuid.UUID, actor: Actor = Depends(require("customers")), db: Session = Depends(get_db)):
    car = _own(db, actor, Car, car_id, "Car")
    owners = tuple(db.scalars(select(CarOwnership).where(CarOwnership.car_id == car.id)))
    return _remove(db, car, "car", owners)


@router.delete("/quotations/{quotation_id}")
def delete_quotation(quotation_id: uuid.UUID, actor: Actor = Depends(require("quotations")), db: Session = Depends(get_db)):
    q = _own(db, actor, Quotation, quotation_id, "Quotation")
    if q.status != "draft":
        raise HTTPException(409, "Only a draft quotation can be deleted. A sent one is rejected or revised, so the record stays.")
    return _remove(db, q, "quotation")


@router.delete("/purchase-orders/{po_id}")
def delete_purchase_order(po_id: uuid.UUID, actor: Actor = Depends(require("purchasing")), db: Session = Depends(get_db)):
    po = _own(db, actor, PurchaseOrder, po_id, "Purchase order")
    if po.status != "draft":
        raise HTTPException(409, "Only a draft order can be deleted. A sent order is cancelled, so the record stays.")
    return _remove(db, po, "purchase order")
