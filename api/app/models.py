from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
    select,
)
from sqlalchemy.orm import (
    Mapped,
    Session,
    backref,
    mapped_column,
    object_session,
    relationship,
)

from app.db import Base

# Keep in sync with app.foundation.branch.DEFAULT_BRANCH_ID (avoid circular import).
DEFAULT_BRANCH_ID = "a1b2c3d4"


def _clock(value: datetime | date | None, fmt: str) -> str | None:
    return value.strftime(fmt) if value else None


class FoundationMixin:
    """Additive columns for branch scoping, optimistic lock, and soft delete.

    Actor columns (`created_by` / `updated_by` / `*_user`) stay on tables that
    already define them — do not redeclare here (avoids mapper conflicts).
    """

    branch_id: Mapped[str | None] = mapped_column(String(8), index=True, default=DEFAULT_BRANCH_ID)
    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Branch(Base):
    __tablename__ = "branch"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "is_default": self.is_default,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


class User(FoundationMixin, Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime)

    def set_password(self, password: str) -> None:
        from app.security import hash_password

        self.password_hash = hash_password(password)

    def check_password(self, password: str) -> bool:
        from app.security import verify_password

        return verify_password(password, self.password_hash)

    def has_permission(self, required_role: str) -> bool:
        role_hierarchy = {
            "admin": [
                "admin",
                "accountant",
                "inventory_manager",
                "repair_orders",
                "repair-order",
                "repair-orders-management",
            ],
            "accountant": [
                "accountant",
                "repair_orders",
                "repair-order",
                "repair-orders-management",
            ],
            "inventory_manager": [
                "inventory_manager",
                "repair_orders",
                "repair-order",
                "repair-orders-management",
            ],
        }
        return required_role in role_hierarchy.get(self.role, [])


class AppLog(Base):
    __tablename__ = "app_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    username: Mapped[str | None] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(100))
    module: Mapped[str] = mapped_column(String(50))
    reference_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(String(255))
    branch_id: Mapped[str | None] = mapped_column(String(8), index=True, default=DEFAULT_BRANCH_ID)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "module": self.module,
            "reference_id": self.reference_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "branch_id": self.branch_id,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


class Invoice(FoundationMixin, Base):
    __tablename__ = "invoice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_address: Mapped[str] = mapped_column(String(255))
    customer_phone: Mapped[str] = mapped_column(String(20))
    customer_reg_no: Mapped[str] = mapped_column(String(50))
    customer_made: Mapped[str] = mapped_column(String(100))
    customer_mileage: Mapped[str] = mapped_column(String(100))
    customer_vin: Mapped[str | None] = mapped_column(String(17))
    customer_color: Mapped[str | None] = mapped_column(String(50))
    customer_chasis: Mapped[str | None] = mapped_column(String(50))
    # Snapshot text above is historical. These links say who it was for.
    # SET NULL: deleting a customer must not delete their documents.
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), index=True
    )
    car_id: Mapped[int | None] = mapped_column(
        ForeignKey("car.id", ondelete="SET NULL"), index=True
    )
    balance: Mapped[float] = mapped_column(Float)
    advance: Mapped[float] = mapped_column(Float)
    net_total: Mapped[float] = mapped_column(Float)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    type_of: Mapped[str] = mapped_column(String(50))
    include_tax: Mapped[bool] = mapped_column(Boolean, default=False)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)
    paid_amount: Mapped[float | None] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    updated_by_user: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    payments_history: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[InvoiceItem]] = relationship(
        "InvoiceItem", backref="invoice", cascade="all, delete-orphan"
    )
    labours: Mapped[list[InvoiceLabour]] = relationship(
        "InvoiceLabour", backref="invoice", cascade="all, delete-orphan"
    )


class InvoiceItem(FoundationMixin, Base):
    __tablename__ = "invoice_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"))
    product_name: Mapped[str] = mapped_column(String(255))
    part_number: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)


class InvoiceLabour(FoundationMixin, Base):
    __tablename__ = "invoice_labour"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"))
    description: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)


class Inventory(FoundationMixin, Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(20), unique=True)
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True)
    manufacturer_part_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    reorder_level: Mapped[int] = mapped_column(Integer, default=5)
    reorder_quantity: Mapped[int] = mapped_column(Integer, default=10)
    image_path: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def generate_part_number(self) -> str:
        """Next unused PN### code.

        SQL MAX(part_number) is lexicographic, so past PN999 it sticks on PN999
        and every new row collides. Scan the numeric suffix instead.
        """
        session = object_session(self)
        if session is None:
            raise RuntimeError("Inventory must be attached to a session to generate a part number")

        used: set[str] = set()
        with session.no_autoflush:
            for part_number in session.scalars(select(Inventory.part_number)):
                if part_number:
                    used.add(part_number)
            for obj in session.new:
                if isinstance(obj, Inventory) and obj.part_number:
                    used.add(obj.part_number)

        max_num = 0
        for part_number in used:
            if not str(part_number).startswith("PN"):
                continue
            suffix = str(part_number)[2:]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))

        next_num = max_num + 1
        while f"PN{next_num:03d}" in used:
            next_num += 1
        return f"PN{next_num:03d}"


class Customer(FoundationMixin, Base):
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    cars: Mapped[list[Car]] = relationship(
        "Car", backref="customer", cascade="all, delete-orphan"
    )

    @property
    def code(self) -> str:
        return f"CN{self.id:03d}" if self.id else ""


class Car(FoundationMixin, Base):
    __tablename__ = "car"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    make: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    plate_no: Mapped[str | None] = mapped_column(String(20))
    mileage: Mapped[str | None] = mapped_column(String(50))
    vin: Mapped[str | None] = mapped_column(String(17))
    color: Mapped[str | None] = mapped_column(String(50))
    chasis_no: Mapped[str | None] = mapped_column(String(50))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customer.id"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    ownership_transfers: Mapped[list["CarOwnership"]] = relationship(
        "CarOwnership",
        back_populates="car",
        cascade="all, delete-orphan",
        order_by="CarOwnership.transfer_date.desc(), CarOwnership.id.desc()",
    )


class RepairOrder(FoundationMixin, Base):
    __tablename__ = "repair_order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_phone: Mapped[str] = mapped_column(String(20))
    customer_address: Mapped[str] = mapped_column(String(255))
    customer_reg_no: Mapped[str] = mapped_column(String(50))
    customer_made: Mapped[str] = mapped_column(String(100))
    customer_mileage: Mapped[str] = mapped_column(String(100))
    customer_vin: Mapped[str | None] = mapped_column(String(17))
    customer_color: Mapped[str | None] = mapped_column(String(50))
    customer_chasis: Mapped[str | None] = mapped_column(String(50))
    problem_description: Mapped[str | None] = mapped_column(Text)
    diagnosis_plan: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.id"))
    worker_name: Mapped[str | None] = mapped_column(String(255))
    current_status: Mapped[str] = mapped_column(String(20), default="received")
    status_timeline: Mapped[str | None] = mapped_column(Text)
    vehicle_condition: Mapped[str | None] = mapped_column(Text)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), index=True
    )
    car_id: Mapped[int | None] = mapped_column(
        ForeignKey("car.id", ondelete="SET NULL"), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    updated_by_user: Mapped[str | None] = mapped_column(String(80))
    workers_json: Mapped[str | None] = mapped_column(Text)

    parts: Mapped[list[RepairOrderPart]] = relationship(
        "RepairOrderPart", backref="repair_order", cascade="all, delete-orphan"
    )
    labour: Mapped[list[RepairOrderLabour]] = relationship(
        "RepairOrderLabour", backref="repair_order", cascade="all, delete-orphan"
    )


class RepairOrderPart(FoundationMixin, Base):
    __tablename__ = "repair_order_part"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repair_order_id: Mapped[int] = mapped_column(ForeignKey("repair_order.id"))
    inventory_id: Mapped[int | None] = mapped_column(ForeignKey("inventory.id"))
    description: Mapped[str] = mapped_column(String(255))
    part_number: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending")


class RepairOrderLabour(FoundationMixin, Base):
    __tablename__ = "repair_order_labour"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repair_order_id: Mapped[int] = mapped_column(ForeignKey("repair_order.id"))
    description: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")


class Expense(FoundationMixin, Base):
    __tablename__ = "expense"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class CashReceived(FoundationMixin, Base):
    __tablename__ = "cash_received"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoice.id"), index=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    invoice: Mapped[Invoice | None] = relationship("Invoice", backref="cash_receipts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "description": self.description,
            "amount": self.amount,
            "payment_method": self.payment_method,
            "notes": self.notes,
            "invoice_id": self.invoice_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FinancialPeriod(FoundationMixin, Base):
    __tablename__ = "financial_periods"
    __table_args__ = (UniqueConstraint("year", "month", name="uq_financial_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    is_open: Mapped[bool] = mapped_column(Boolean, default=False)
    changed_by: Mapped[str | None] = mapped_column(String(80))
    changed_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    reason: Mapped[str | None] = mapped_column(String(255))

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "month": self.month,
            "is_open": self.is_open,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "reason": self.reason,
        }


class WhatsAppNotification(FoundationMixin, Base):
    __tablename__ = "whats_app_notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_phone: Mapped[str] = mapped_column(String(20))
    notification_type: Mapped[str] = mapped_column(String(50))
    message_content: Mapped[str] = mapped_column(Text)
    related_document_type: Mapped[str | None] = mapped_column(String(50))
    related_document_id: Mapped[int | None] = mapped_column(Integer)
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)

    def mark_sent(self, message_id: str | None = None) -> None:
        self.status = "sent"
        self.whatsapp_message_id = message_id
        self.sent_at = datetime.utcnow()
        self.error_message = None

    def mark_failed(self, error: str | None = None) -> None:
        self.status = "failed"
        self.error_message = error

    def mark_delivered(self) -> None:
        self.status = "delivered"
        self.delivered_at = datetime.utcnow()

    def to_dict(self) -> dict:
        def stamp(value: datetime | None) -> str | None:
            return value.isoformat() if value else None

        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "notification_type": self.notification_type,
            "message_content": self.message_content,
            "related_document_type": self.related_document_type,
            "related_document_id": self.related_document_id,
            "whatsapp_message_id": self.whatsapp_message_id,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": stamp(self.created_at),
            "sent_at": stamp(self.sent_at),
            "delivered_at": stamp(self.delivered_at),
        }


class Vendor(FoundationMixin, Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str] = mapped_column(String(255))
    contact_person: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(Text)
    cnic: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    ledger_entries: Mapped[list[VendorLedger]] = relationship(
        "VendorLedger", backref="vendor", cascade="all, delete-orphan"
    )
    purchase_orders: Mapped[list[PurchaseOrder]] = relationship(
        "PurchaseOrder", backref="vendor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Vendor {self.name} - {self.company_name}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "company_name": self.company_name,
            "contact_person": self.contact_person,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "cnic": self.cnic,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class VendorLedger(FoundationMixin, Base):
    __tablename__ = "vendor_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500))
    folio: Mapped[str | None] = mapped_column(String(100))
    debit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    payment_notes: Mapped[str | None] = mapped_column(Text)
    attachment_path: Mapped[str | None] = mapped_column(String(255))

    def __repr__(self) -> str:
        return f"<VendorLedger {self.vendor_id} - {self.description}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vendor_id": self.vendor_id,
            "date": self.date.strftime("%Y-%m-%d"),
            "description": self.description,
            "folio": self.folio,
            "debit": float(self.debit),
            "credit": float(self.credit),
            "balance": float(self.balance),
            "created_by_user": self.created_by_user,
            "payment_notes": self.payment_notes,
            "attachment_path": self.attachment_path,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class PurchaseOrder(FoundationMixin, Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    date: Mapped[date] = mapped_column(Date)
    invoice_no: Mapped[str] = mapped_column(String(100))
    item_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    remarks: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="ordered")
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<PurchaseOrder {self.vendor_id} - {self.item_name}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vendor_id": self.vendor_id,
            "date": self.date.strftime("%Y-%m-%d"),
            "invoice_no": self.invoice_no,
            "item_name": self.item_name,
            "quantity": self.quantity,
            "rate": float(self.rate),
            "amount": float(self.amount),
            "remarks": self.remarks,
            "status": self.status,
            "created_by_user": self.created_by_user,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": _clock(self.updated_at, "%Y-%m-%d %H:%M:%S"),
        }


class Worker(FoundationMixin, Base):
    __tablename__ = "workers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(Text)
    cnic: Mapped[str] = mapped_column(String(20), unique=True)
    date_of_birth: Mapped[date] = mapped_column(Date)
    hire_date: Mapped[date] = mapped_column(Date)
    position: Mapped[str] = mapped_column(String(100))
    department: Mapped[str] = mapped_column(String(100))
    salary: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20), default="active")
    emergency_contact_name: Mapped[str | None] = mapped_column(String(100))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Worker {self.employee_id} - {self.first_name} {self.last_name}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "cnic": self.cnic,
            "date_of_birth": _clock(self.date_of_birth, "%Y-%m-%d"),
            "hire_date": _clock(self.hire_date, "%Y-%m-%d"),
            "position": self.position,
            "department": self.department,
            "salary": float(self.salary) if self.salary else None,
            "status": self.status,
            "emergency_contact_name": self.emergency_contact_name,
            "emergency_contact_phone": self.emergency_contact_phone,
            "notes": self.notes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class SalaryAdvance(FoundationMixin, Base):
    __tablename__ = "salary_advances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[int] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    payment_method: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    worker: Mapped[Worker] = relationship(
        "Worker",
        backref=backref("salary_advances", lazy="dynamic", cascade="all, delete-orphan"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "worker_name": f"{self.worker.first_name} {self.worker.last_name}" if self.worker else None,
            "employee_id": self.worker.employee_id if self.worker else None,
            "date": self.date.strftime("%Y-%m-%d"),
            "amount": float(self.amount),
            "payment_method": self.payment_method,
            "notes": self.notes,
            "created_by": self.created_by,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


class PayrollRun(FoundationMixin, Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("worker_id", "year", "month", name="uq_payroll_worker_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[int] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    earned_salary: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    advances_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    net_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expense.id", ondelete="SET NULL"))
    run_by: Mapped[str | None] = mapped_column(String(100))
    run_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    worker: Mapped[Worker] = relationship(
        "Worker", backref=backref("payroll_runs", lazy="dynamic")
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "worker_name": f"{self.worker.first_name} {self.worker.last_name}" if self.worker else None,
            "employee_id": self.worker.employee_id if self.worker else None,
            "year": self.year,
            "month": self.month,
            "earned_salary": float(self.earned_salary),
            "advances_total": float(self.advances_total or 0),
            "net_paid": float(self.net_paid),
            "expense_id": self.expense_id,
            "run_by": self.run_by,
            "run_at": _clock(self.run_at, "%Y-%m-%d %H:%M:%S"),
        }


class AttendanceRecord(FoundationMixin, Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"))
    date: Mapped[date] = mapped_column(Date)
    check_in_time: Mapped[datetime | None] = mapped_column(DateTime)
    check_out_time: Mapped[datetime | None] = mapped_column(DateTime)
    work_hours: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(50))
    zkteco_device_id: Mapped[int | None] = mapped_column(ForeignKey("zkteco_devices.id"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    worker: Mapped[Worker] = relationship(
        "Worker", backref=backref("attendance_records", lazy="dynamic")
    )
    zkteco_device: Mapped[ZKTecoDevice | None] = relationship(
        "ZKTecoDevice", backref=backref("attendance_records", lazy="dynamic")
    )

    def __repr__(self) -> str:
        return f"<AttendanceRecord worker_id={self.worker_id} date={self.date}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "date": _clock(self.date, "%Y-%m-%d"),
            "check_in_time": _clock(self.check_in_time, "%H:%M"),
            "check_out_time": _clock(self.check_out_time, "%H:%M"),
            "work_hours": round(self.work_hours, 2) if self.work_hours is not None else None,
            "notes": self.notes,
            "source": self.source,
            "zkteco_device_id": self.zkteco_device_id,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class ZKTecoDevice(FoundationMixin, Base):
    __tablename__ = "zkteco_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    serial_number: Mapped[str | None] = mapped_column(String(64), unique=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    port: Mapped[int | None] = mapped_column(Integer, default=4370)
    timeout: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime)
    last_sync_status: Mapped[str | None] = mapped_column(String(50))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        addr = f"{self.ip_address}:{self.port}" if self.ip_address else (self.serial_number or "?")
        return f"<ZKTecoDevice {self.name} {addr}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "serial_number": self.serial_number,
            "ip_address": self.ip_address,
            "port": self.port,
            "timeout": self.timeout,
            "is_active": self.is_active,
            "last_sync": _clock(self.last_sync, "%Y-%m-%d %H:%M:%S"),
            "last_sync_status": self.last_sync_status,
            "last_seen_at": _clock(self.last_seen_at, "%Y-%m-%d %H:%M:%S"),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class Department(FoundationMixin, Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Department {self.name}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class Category(FoundationMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Category {self.name}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class InventoryTransaction(FoundationMixin, Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory.id"))
    transaction_type: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)
    previous_quantity: Mapped[int] = mapped_column(Integer)
    new_quantity: Mapped[int] = mapped_column(Integer)
    repair_order_id: Mapped[int | None] = mapped_column(ForeignKey("repair_order.id"))
    reference_description: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text)

    inventory: Mapped[Inventory] = relationship("Inventory", backref="transactions")
    repair_order: Mapped[RepairOrder | None] = relationship(
        "RepairOrder", backref="inventory_transactions"
    )
    user: Mapped[User | None] = relationship("User", backref="inventory_transactions")

    def __repr__(self) -> str:
        return f"<InventoryTransaction {self.id} - {self.transaction_type} - {self.quantity}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "inventory_id": self.inventory_id,
            "inventory_name": self.inventory.name if self.inventory else None,
            "inventory_part_number": self.inventory.part_number if self.inventory else None,
            "transaction_type": self.transaction_type,
            "quantity": self.quantity,
            "previous_quantity": self.previous_quantity,
            "new_quantity": self.new_quantity,
            "repair_order_id": self.repair_order_id,
            "reference_description": self.reference_description,
            "created_by": self.created_by,
            "created_by_username": self.user.username if self.user else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "notes": self.notes,
        }


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role", "permission", name="unique_role_permission"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[str] = mapped_column(String(50))
    permission: Mapped[str] = mapped_column(String(100))

    def to_dict(self) -> dict:
        return {"id": self.id, "role": self.role, "permission": self.permission}


class Attachment(FoundationMixin, Base):
    """Reusable evidence file linked to any entity_type + entity_id."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, index=True)
    file_path: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(120))
    uploaded_by: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "branch_id": self.branch_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "file_path": self.file_path,
            "original_name": self.original_name,
            "content_type": self.content_type,
            "uploaded_by": self.uploaded_by,
            "notes": self.notes,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


class CarOwnership(FoundationMixin, Base):
    """Ownership transfer. History stays on the car; invoices keep the original customer."""

    __tablename__ = "car_ownership"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("car.id"), index=True)
    from_customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True, index=True
    )
    to_customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)
    transfer_date: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str] = mapped_column(String(255))
    evidence_attachment_id: Mapped[int] = mapped_column(ForeignKey("attachments.id"))
    transferred_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    car: Mapped[Car] = relationship("Car", back_populates="ownership_transfers")
    from_customer: Mapped[Customer | None] = relationship(
        "Customer", foreign_keys=[from_customer_id]
    )
    to_customer: Mapped[Customer] = relationship("Customer", foreign_keys=[to_customer_id])
    evidence: Mapped[Attachment] = relationship(
        "Attachment", foreign_keys=[evidence_attachment_id]
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "car_id": self.car_id,
            "from_customer_id": self.from_customer_id,
            "from_customer_name": self.from_customer.name if self.from_customer else None,
            "to_customer_id": self.to_customer_id,
            "to_customer_name": self.to_customer.name if self.to_customer else None,
            "transfer_date": self.transfer_date.isoformat() if self.transfer_date else None,
            "reason": self.reason,
            "evidence_attachment_id": self.evidence_attachment_id,
            "evidence_path": self.evidence.file_path if self.evidence else None,
            "transferred_by": self.transferred_by,
            "branch_id": self.branch_id,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


class IdempotencyKey(Base):
    """Create-endpoint idempotency: same key returns the original response."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("branch_id", "key", name="uq_idempotency_branch_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_id: Mapped[str] = mapped_column(String(8), default=DEFAULT_BRANCH_ID)
    key: Mapped[str] = mapped_column(String(128))
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(255))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(80))


def _needs_part_number(obj: object) -> bool:
    if not isinstance(obj, Inventory) or obj.part_number:
        return False
    state = inspect(obj)
    return bool(state.transient or state.pending)


@event.listens_for(Session, "before_flush")
def _part_number_before_flush(session: Session, flush_context, instances) -> None:
    for obj in list(session.new):
        if _needs_part_number(obj):
            obj.part_number = obj.generate_part_number()


def _demo() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SASession

    demo_engine = create_engine("sqlite://")
    Base.metadata.create_all(demo_engine)
    with SASession(demo_engine) as db:
        first = Inventory(name="Pad", category="Brakes")
        second = Inventory(name="Rotor", category="Brakes")
        db.add_all([first, second])
        db.flush()
        assert (first.part_number, second.part_number) == ("PN001", "PN002")
        db.add(Inventory(name="Legacy", category="Brakes", part_number="PN1000"))
        db.flush()
        nxt = Inventory(name="Next", category="Brakes")
        db.add(nxt)
        db.flush()
        assert nxt.part_number == "PN1001", nxt.part_number
        customer = Customer(name="Noman")
        db.add(customer)
        db.flush()
        assert customer.code == "CN001"
    print("models ok")


if __name__ == "__main__":
    _demo()
