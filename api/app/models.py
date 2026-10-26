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
    document_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
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
    # Pipeline linkage (additive)
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_card_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_cards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    repair_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("repair_order.id", ondelete="SET NULL"), nullable=True, index=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parent_quote_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_variation: Mapped[bool] = mapped_column(Boolean, default=False)

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
    proposed_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    inventory_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory.id", ondelete="SET NULL"), nullable=True
    )
    job_card_line_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | approved | rejected


class InvoiceLabour(FoundationMixin, Base):
    __tablename__ = "invoice_labour"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"))
    description: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)
    proposed_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    labour_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("labour_codes.id", ondelete="SET NULL"), nullable=True
    )
    std_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    job_card_line_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="pending")


class Inventory(FoundationMixin, Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(20), unique=True)
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True)
    manufacturer_part_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, default=0)  # on_hand
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(Float, default=0.0)  # sell price (legacy)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    reorder_level: Mapped[int] = mapped_column(Integer, default=5)  # min_level alias
    reorder_quantity: Mapped[int] = mapped_column(Integer, default=10)
    min_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Store / UOM — stock qty is always stored in base pieces
    unit: Mapped[str] = mapped_column(String(20), default="pcs")
    pack_size: Mapped[int] = mapped_column(Integer, default=1)  # pieces per pack (1 = no packs)
    valuation_method: Mapped[str] = mapped_column(String(20), default="avg")  # avg (FIFO later)
    preferred_vendor_id: Mapped[int | None] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    superseded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory.id"), nullable=True
    )
    alternate_codes: Mapped[str | None] = mapped_column(Text)  # comma-separated cross-refs
    pending_purchase: Mapped[bool] = mapped_column(Boolean, default=False)
    image_path: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    superseded_by: Mapped["Inventory | None"] = relationship(
        "Inventory",
        remote_side="Inventory.id",
        foreign_keys=[superseded_by_id],
        uselist=False,
    )

    @property
    def on_hand(self) -> int:
        return int(self.quantity or 0)

    @property
    def available(self) -> int:
        return int(self.quantity or 0) - int(self.reserved or 0)

    @property
    def qty_available(self) -> int:
        """Alias for pipeline / shortage helpers."""
        return self.available

    @property
    def qty_reserved(self) -> int:
        """Alias for pipeline parts_flow (column is ``reserved``)."""
        return int(self.reserved or 0)

    @qty_reserved.setter
    def qty_reserved(self, value: int) -> None:
        self.reserved = int(value or 0)

    @property
    def effective_min_level(self) -> int:
        if self.min_level is not None:
            return int(self.min_level)
        return int(self.reorder_level or 0)

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
    code: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    alternate_phone: Mapped[str | None] = mapped_column(String(20), index=True)
    address: Mapped[str | None] = mapped_column(String(255))
    customer_type: Mapped[str | None] = mapped_column(String(40), default="retail")
    notes: Mapped[str | None] = mapped_column(Text)
    # Communication preferences / consent (WhatsApp, SMS, call)
    consent_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_sms: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_call: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    updated_by_user: Mapped[str | None] = mapped_column(String(80))

    # No delete-orphan: vehicles keep history/ownership when detached from a customer.
    cars: Mapped[list[Car]] = relationship("Car", backref="customer")


class Car(FoundationMixin, Base):
    __tablename__ = "car"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    make: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plate_no: Mapped[str | None] = mapped_column(String(20), index=True)
    mileage: Mapped[str | None] = mapped_column(String(50))
    vin: Mapped[str | None] = mapped_column(String(17), index=True)
    color: Mapped[str | None] = mapped_column(String(50))
    chasis_no: Mapped[str | None] = mapped_column(String(50))
    engine_no: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    updated_by_user: Mapped[str | None] = mapped_column(String(80))

    ownership_transfers: Mapped[list["CarOwnership"]] = relationship(
        "CarOwnership",
        back_populates="car",
        cascade="all, delete-orphan",
        order_by="CarOwnership.transfer_date.desc(), CarOwnership.id.desc()",
    )


class RepairOrder(FoundationMixin, Base):
    __tablename__ = "repair_order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
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
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_card_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_cards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    quote_invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True, index=True
    )
    qc_signoff_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payment_gate_bypassed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Repair execution (additive)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_for_qc_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    labour_cost_total: Mapped[float] = mapped_column(Float, default=0.0)
    parts_cost_total: Mapped[float] = mapped_column(Float, default=0.0)

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
    qty_reserved: Mapped[int] = mapped_column(Integer, default=0)
    qty_issued: Mapped[int] = mapped_column(Integer, default=0)
    qty_returned: Mapped[int] = mapped_column(Integer, default=0)
    from_variation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # shop_stock | customer_supplied — customer-supplied: labour only, no stock/margin
    ownership_type: Mapped[str] = mapped_column(String(30), default="shop_stock")
    old_parts_returned: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_status: Mapped[str] = mapped_column(String(20), default="approved")
    unit_cost: Mapped[float | None] = mapped_column(Float, nullable=True)


class RepairOrderLabour(FoundationMixin, Base):
    __tablename__ = "repair_order_labour"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repair_order_id: Mapped[int] = mapped_column(ForeignKey("repair_order.id"))
    description: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    labour_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("labour_codes.id", ondelete="SET NULL"), nullable=True
    )
    from_variation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Repair execution (additive) — actual_hours feed job cost, NOT payroll
    assigned_worker_id: Mapped[int | None] = mapped_column(
        ForeignKey("workers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    approval_status: Mapped[str] = mapped_column(String(20), default="approved")
    std_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_hours: Mapped[float] = mapped_column(Float, default=0.0)
    labour_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    labour_cost: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    line_notes: Mapped[str | None] = mapped_column(Text)


class Expense(FoundationMixin, Base):
    __tablename__ = "expense"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    updated_by_user: Mapped[str | None] = mapped_column(String(80))


class CashReceived(FoundationMixin, Base):
    __tablename__ = "cash_received"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
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
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    updated_by_user: Mapped[str | None] = mapped_column(String(80))

    invoice: Mapped[Invoice | None] = relationship("Invoice", backref="cash_receipts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_no": self.document_no,
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
    code: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str] = mapped_column(String(255))
    contact_person: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(Text)
    cnic: Mapped[str | None] = mapped_column(String(20))
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    bank_details: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    updated_by_user: Mapped[str | None] = mapped_column(String(80))

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
            "code": self.code,
            "name": self.name,
            "company_name": self.company_name,
            "contact_person": self.contact_person,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "cnic": self.cnic,
            "payment_terms_days": int(self.payment_terms_days or 30),
            "bank_details": self.bank_details,
            "notes": self.notes,
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
    # Soft links to AP docs (no FK — avoids circular create_all cycles)
    supplier_invoice_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    supplier_payment_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    supplier_credit_note_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    goods_receipt_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<VendorLedger {self.vendor_id} - {self.description}>"

    def to_dict(self) -> dict:
        debit = float(self.debit or 0)
        credit = float(self.credit or 0)
        entry_type = "debit" if debit > 0 and credit == 0 else "credit" if credit > 0 else "mixed"
        return {
            "id": self.id,
            "vendor_id": self.vendor_id,
            "date": self.date.strftime("%Y-%m-%d"),
            "description": self.description,
            "folio": self.folio,
            "debit": debit,
            "credit": credit,
            "entry_type": entry_type,
            "amount": debit if debit > 0 else credit,
            "balance": float(self.balance),
            "created_by_user": self.created_by_user,
            "payment_notes": self.payment_notes,
            "attachment_path": self.attachment_path,
            "supplier_invoice_id": self.supplier_invoice_id,
            "supplier_payment_id": self.supplier_payment_id,
            "supplier_credit_note_id": self.supplier_credit_note_id,
            "goods_receipt_id": self.goods_receipt_id,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class CustomerLedger(FoundationMixin, Base):
    """Customer AR: debit on invoice finalize (accrual), credit on verified payment / CN."""

    __tablename__ = "customer_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500))
    folio: Mapped[str | None] = mapped_column(String(100))
    debit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True, index=True
    )
    credit_note_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    cash_received_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    payment_notes: Mapped[str | None] = mapped_column(Text)

    def to_dict(self) -> dict:
        debit = float(self.debit or 0)
        credit = float(self.credit or 0)
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "date": self.date.strftime("%Y-%m-%d") if self.date else None,
            "description": self.description,
            "folio": self.folio,
            "debit": debit,
            "credit": credit,
            "balance": float(self.balance or 0),
            "invoice_id": self.invoice_id,
            "credit_note_id": self.credit_note_id,
            "cash_received_id": self.cash_received_id,
            "created_by_user": self.created_by_user,
            "payment_notes": self.payment_notes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class CustomerCreditNote(FoundationMixin, Base):
    """Authorized reduction of a posted customer invoice (not a new invoice rewrite)."""

    __tablename__ = "customer_credit_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="posted")
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "customer_id": self.customer_id,
            "amount": float(self.amount or 0),
            "reason": self.reason,
            "status": self.status,
            "created_by_user": self.created_by_user,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class PurchaseOrder(FoundationMixin, Base):
    """PO workflow: draft → approved → ordered → partial/received → closed.

    Commitment only — does not increase stock or create a payable.
    `quantity` = ordered qty; `qty_received` accumulates GRNs.
    Cost/avg cost updates only on receive (see app.stock.po_receive).
    """

    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    inventory_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory.id", ondelete="SET NULL"), nullable=True, index=True
    )
    date: Mapped[date] = mapped_column(Date)
    expected_delivery: Mapped[date | None] = mapped_column(Date, nullable=True)
    invoice_no: Mapped[str] = mapped_column(String(100))
    item_name: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)
    qty_received: Mapped[int] = mapped_column(Integer, default=0)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    remarks: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by_user: Mapped[str | None] = mapped_column(String(80))
    job_card_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    quote_invoice_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    receipt_attachment_path: Mapped[str | None] = mapped_column(String(255))
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    updated_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    inventory: Mapped[Inventory | None] = relationship("Inventory")

    def __repr__(self) -> str:
        return f"<PurchaseOrder {self.vendor_id} - {self.item_name}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_no": self.document_no,
            "vendor_id": self.vendor_id,
            "inventory_id": self.inventory_id,
            "date": self.date.strftime("%Y-%m-%d"),
            "expected_delivery": _clock(self.expected_delivery, "%Y-%m-%d"),
            "invoice_no": self.invoice_no,
            "item_name": self.item_name,
            "unit": self.unit,
            "quantity": self.quantity,
            "qty_received": int(self.qty_received or 0),
            "qty_remaining": max(0, int(self.quantity or 0) - int(self.qty_received or 0)),
            "rate": float(self.rate),
            "amount": float(self.amount),
            "remarks": self.remarks,
            "status": self.status,
            "approved_at": _clock(self.approved_at, "%Y-%m-%d %H:%M:%S"),
            "approved_by_user": self.approved_by_user,
            "job_card_id": self.job_card_id,
            "quote_invoice_id": self.quote_invoice_id,
            "receipt_attachment_path": self.receipt_attachment_path,
            "created_by_user": self.created_by_user,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": _clock(self.updated_at, "%Y-%m-%d %H:%M:%S"),
        }


class GoodsReceipt(FoundationMixin, Base):
    """GRN — increases stock. Does not create a payable by itself."""

    __tablename__ = "goods_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id"), index=True
    )
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory.id"), index=True)
    inventory_transaction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supplier_invoice_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer)
    verified_qty: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    receipt_attachment_path: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="received")  # received|invoiced|returned
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_no": self.document_no,
            "purchase_order_id": self.purchase_order_id,
            "vendor_id": self.vendor_id,
            "inventory_id": self.inventory_id,
            "inventory_transaction_id": self.inventory_transaction_id,
            "supplier_invoice_id": self.supplier_invoice_id,
            "date": self.date.strftime("%Y-%m-%d"),
            "quantity": self.quantity,
            "verified_qty": self.verified_qty,
            "unit_cost": float(self.unit_cost),
            "amount": float(self.amount),
            "receipt_attachment_path": self.receipt_attachment_path,
            "status": self.status,
            "notes": self.notes,
            "created_by_user": self.created_by_user,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


class SupplierInvoice(FoundationMixin, Base):
    """Supplier invoice — creates the payable (VendorLedger debit)."""

    __tablename__ = "supplier_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    goods_receipt_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    vendor_ledger_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supplier_invoice_no: Mapped[str] = mapped_column(String(100))
    date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(30), default="open")  # open|partial|paid|void
    notes: Mapped[str | None] = mapped_column(Text)
    attachment_path: Mapped[str | None] = mapped_column(String(255))
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        amount = float(self.amount or 0)
        paid = float(self.amount_paid or 0)
        return {
            "id": self.id,
            "document_no": self.document_no,
            "vendor_id": self.vendor_id,
            "purchase_order_id": self.purchase_order_id,
            "goods_receipt_id": self.goods_receipt_id,
            "vendor_ledger_id": self.vendor_ledger_id,
            "supplier_invoice_no": self.supplier_invoice_no,
            "date": self.date.strftime("%Y-%m-%d"),
            "due_date": _clock(self.due_date, "%Y-%m-%d"),
            "amount": amount,
            "amount_paid": paid,
            "amount_due": max(0.0, amount - paid),
            "status": self.status,
            "notes": self.notes,
            "attachment_path": self.attachment_path,
            "created_by_user": self.created_by_user,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


class SupplierPayment(FoundationMixin, Base):
    """Supplier payment — reduces payable (VendorLedger credit). Not a repurchase."""

    __tablename__ = "supplier_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    supplier_invoice_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    vendor_ledger_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    method: Mapped[str | None] = mapped_column(String(40))  # cash|bank|cheque
    reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    attachment_path: Mapped[str | None] = mapped_column(String(255))
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_no": self.document_no,
            "vendor_id": self.vendor_id,
            "supplier_invoice_id": self.supplier_invoice_id,
            "vendor_ledger_id": self.vendor_ledger_id,
            "date": self.date.strftime("%Y-%m-%d"),
            "amount": float(self.amount),
            "method": self.method,
            "reference": self.reference,
            "notes": self.notes,
            "attachment_path": self.attachment_path,
            "created_by_user": self.created_by_user,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


class SupplierCreditNote(FoundationMixin, Base):
    """Return / credit note / refund against a GRN or invoice."""

    __tablename__ = "supplier_credit_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    goods_receipt_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    supplier_invoice_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    inventory_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory.id", ondelete="SET NULL"), nullable=True
    )
    inventory_transaction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vendor_ledger_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="posted")  # posted|void
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_no": self.document_no,
            "vendor_id": self.vendor_id,
            "purchase_order_id": self.purchase_order_id,
            "goods_receipt_id": self.goods_receipt_id,
            "supplier_invoice_id": self.supplier_invoice_id,
            "inventory_id": self.inventory_id,
            "inventory_transaction_id": self.inventory_transaction_id,
            "vendor_ledger_id": self.vendor_ledger_id,
            "date": self.date.strftime("%Y-%m-%d"),
            "quantity": self.quantity,
            "unit_cost": float(self.unit_cost or 0),
            "amount": float(self.amount),
            "refund_amount": float(self.refund_amount or 0),
            "reason": self.reason,
            "status": self.status,
            "notes": self.notes,
            "created_by_user": self.created_by_user,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
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
    """StockMovement ledger (legacy table name kept for existing data).

    Types: po_receive, reserve, release, issue_to_ro, return_from_ro,
    adjustment, wastage, opening (+ legacy issue_out / received).
    """

    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory.id"))
    transaction_type: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[int] = mapped_column(Integer)
    previous_quantity: Mapped[int] = mapped_column(Integer)
    new_quantity: Mapped[int] = mapped_column(Integer)
    reserved_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reserved_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    repair_order_id: Mapped[int | None] = mapped_column(ForeignKey("repair_order.id"))
    purchase_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=True
    )
    reference_description: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(String(255))
    evidence_path: Mapped[str | None] = mapped_column(String(255))

    inventory: Mapped[Inventory] = relationship("Inventory", backref="transactions")
    repair_order: Mapped[RepairOrder | None] = relationship(
        "RepairOrder", backref="inventory_transactions"
    )
    purchase_order: Mapped[PurchaseOrder | None] = relationship("PurchaseOrder")
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
            "movement_type": self.transaction_type,
            "quantity": self.quantity,
            "previous_quantity": self.previous_quantity,
            "new_quantity": self.new_quantity,
            "on_hand_before": self.previous_quantity,
            "on_hand_after": self.new_quantity,
            "reserved_before": self.reserved_before,
            "reserved_after": self.reserved_after,
            "unit_cost": float(self.unit_cost) if self.unit_cost is not None else None,
            "repair_order_id": self.repair_order_id,
            "purchase_order_id": self.purchase_order_id,
            "reference_description": self.reference_description,
            "created_by": self.created_by,
            "created_by_username": self.user.username if self.user else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "notes": self.notes,
            "reason": self.reason,
            "evidence_path": self.evidence_path,
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


class InspectionTemplate(FoundationMixin, Base):
    """Configurable multi-point check-in inspection template."""

    __tablename__ = "inspection_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Default check-in")
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # JSON list of {key, label, category, requires_photo, sort_order}
    points_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def points(self) -> list[dict]:
        import json

        try:
            data = json.loads(self.points_json or "[]")
            return data if isinstance(data, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "points": self.points(),
            "branch_id": self.branch_id,
        }


class Visit(FoundationMixin, Base):
    """Vehicle check-in / visit with digital inspection + customer signature."""

    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("car.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True, index=True
    )
    odometer: Mapped[str | None] = mapped_column(String(50))
    fuel_level: Mapped[str | None] = mapped_column(String(40))
    reported_complaints: Mapped[str | None] = mapped_column(Text)
    existing_damage: Mapped[str | None] = mapped_column(Text)
    signature_attachment_id: Mapped[int | None] = mapped_column(
        ForeignKey("attachments.id"), nullable=True
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspection_templates.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="completed")
    is_comeback: Mapped[bool] = mapped_column(Boolean, default=False)
    repair_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("repair_order.id", ondelete="SET NULL"), nullable=True, index=True
    )
    checked_in_by: Mapped[str | None] = mapped_column(String(80))
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    car: Mapped[Car] = relationship("Car", backref="visits")
    customer: Mapped[Customer | None] = relationship("Customer")
    signature: Mapped[Attachment | None] = relationship(
        "Attachment", foreign_keys=[signature_attachment_id]
    )
    items: Mapped[list["VisitInspectionItem"]] = relationship(
        "VisitInspectionItem",
        back_populates="visit",
        cascade="all, delete-orphan",
        order_by="VisitInspectionItem.sort_order",
    )

    def to_dict(self, *, include_items: bool = True) -> dict:
        data = {
            "id": self.id,
            "car_id": self.car_id,
            "customer_id": self.customer_id,
            "customer_name": self.customer.name if self.customer else None,
            "odometer": self.odometer,
            "fuel_level": self.fuel_level,
            "reported_complaints": self.reported_complaints,
            "existing_damage": self.existing_damage,
            "signature_attachment_id": self.signature_attachment_id,
            "signature_path": self.signature.file_path if self.signature else None,
            "template_id": self.template_id,
            "status": self.status,
            "is_comeback": self.is_comeback,
            "repair_order_id": self.repair_order_id,
            "checked_in_by": self.checked_in_by,
            "check_in_at": _clock(self.check_in_at, "%Y-%m-%d %H:%M:%S"),
            "branch_id": self.branch_id,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }
        if include_items:
            data["items"] = [i.to_dict() for i in (self.items or [])]
        return data


class VisitInspectionItem(FoundationMixin, Base):
    """One checklist point on a visit, optionally with a photo."""

    __tablename__ = "visit_inspection_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), index=True)
    point_key: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40), default="general")
    result: Mapped[str] = mapped_column(String(20), default="ok")  # ok | issue | na
    notes: Mapped[str | None] = mapped_column(Text)
    photo_attachment_id: Mapped[int | None] = mapped_column(
        ForeignKey("attachments.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    visit: Mapped[Visit] = relationship("Visit", back_populates="items")
    photo: Mapped[Attachment | None] = relationship(
        "Attachment", foreign_keys=[photo_attachment_id]
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "visit_id": self.visit_id,
            "point_key": self.point_key,
            "label": self.label,
            "category": self.category,
            "result": self.result,
            "notes": self.notes,
            "photo_attachment_id": self.photo_attachment_id,
            "photo_path": self.photo.file_path if self.photo else None,
            "sort_order": self.sort_order,
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


class LabourCode(FoundationMixin, Base):
    """Labour catalogue: code, description, standard hours, rate, category."""

    __tablename__ = "labour_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))
    standard_hours: Mapped[float] = mapped_column(Float, default=1.0)
    rate: Mapped[float] = mapped_column(Float, default=0.0)
    category: Mapped[str] = mapped_column(String(80), default="general")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "description": self.description,
            "standard_hours": self.standard_hours,
            "rate": self.rate,
            "category": self.category,
            "is_active": self.is_active,
            "branch_id": self.branch_id,
            "version": self.version,
        }


class JobCard(FoundationMixin, Base):
    """Job card builds the quotation; not the repair order itself."""

    __tablename__ = "job_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    car_id: Mapped[int | None] = mapped_column(
        ForeignKey("car.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(255), default="")
    customer_phone: Mapped[str] = mapped_column(String(20), default="")
    customer_reg_no: Mapped[str] = mapped_column(String(50), default="")
    customer_made: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="open")
    # open | quoted | closed | cancelled
    notes: Mapped[str | None] = mapped_column(Text)
    quote_invoice_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    lines: Mapped[list["JobCardLine"]] = relationship(
        "JobCardLine",
        back_populates="job_card",
        cascade="all, delete-orphan",
        order_by="JobCardLine.id",
    )

    def to_dict(self, *, include_lines: bool = True) -> dict:
        data = {
            "id": self.id,
            "visit_id": self.visit_id,
            "car_id": self.car_id,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "customer_reg_no": self.customer_reg_no,
            "customer_made": self.customer_made,
            "status": self.status,
            "notes": self.notes,
            "quote_invoice_id": self.quote_invoice_id,
            "created_by_user": self.created_by_user,
            "branch_id": self.branch_id,
            "version": self.version,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }
        if include_lines:
            data["lines"] = [ln.to_dict() for ln in (self.lines or [])]
        return data


class JobCardLine(FoundationMixin, Base):
    __tablename__ = "job_card_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_card_id: Mapped[int] = mapped_column(ForeignKey("job_cards.id"), index=True)
    line_type: Mapped[str] = mapped_column(String(20), default="labour")
    # labour | part
    labour_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("labour_codes.id", ondelete="SET NULL"), nullable=True
    )
    inventory_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(255), default="")
    part_number: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    std_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    pay_type: Mapped[str] = mapped_column(String(20), default="customer")
    # customer | warranty | internal
    assigned_technician: Mapped[str | None] = mapped_column(String(120))
    line_status: Mapped[str] = mapped_column(String(20), default="Pending")
    # Pending, Approved, Rejected, In progress, Done, QC passed
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    job_card: Mapped[JobCard] = relationship("JobCard", back_populates="lines")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_card_id": self.job_card_id,
            "line_type": self.line_type,
            "labour_code_id": self.labour_code_id,
            "inventory_id": self.inventory_id,
            "description": self.description,
            "part_number": self.part_number,
            "quantity": self.quantity,
            "std_hours": self.std_hours,
            "unit_price": self.unit_price,
            "pay_type": self.pay_type,
            "assigned_technician": self.assigned_technician,
            "line_status": self.line_status,
        }


class ApprovalToken(FoundationMixin, Base):
    """Public token for WhatsApp line-wise quote / variation approval."""

    __tablename__ = "approval_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(80))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "token": self.token,
            "invoice_id": self.invoice_id,
            "expires_at": _clock(self.expires_at, "%Y-%m-%d %H:%M:%S"),
            "revoked_at": _clock(self.revoked_at, "%Y-%m-%d %H:%M:%S"),
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


class QuoteLineApproval(FoundationMixin, Base):
    """Per-line customer approval evidence on a quote/variation."""

    __tablename__ = "quote_line_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"), index=True)
    line_kind: Mapped[str] = mapped_column(String(20))  # item | labour
    line_id: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(20))  # approved | rejected
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    client_ip: Mapped[str | None] = mapped_column(String(64))
    token: Mapped[str | None] = mapped_column(String(64))
    media_attachment_id: Mapped[int | None] = mapped_column(
        ForeignKey("attachments.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "line_kind": self.line_kind,
            "line_id": self.line_id,
            "decision": self.decision,
            "decided_at": _clock(self.decided_at, "%Y-%m-%d %H:%M:%S"),
            "client_ip": self.client_ip,
            "token": self.token,
            "media_attachment_id": self.media_attachment_id,
            "notes": self.notes,
        }


class CustomerDeposit(FoundationMixin, Base):
    """Customer advance as liability; converts to revenue only when applied to invoice."""

    __tablename__ = "customer_deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True, index=True
    )
    quote_invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True, index=True
    )
    applied_invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="open")
    # open | applied | refunded | adjusted
    evidence_attachment_id: Mapped[int | None] = mapped_column(
        ForeignKey("attachments.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(255))
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "visit_id": self.visit_id,
            "customer_id": self.customer_id,
            "quote_invoice_id": self.quote_invoice_id,
            "applied_invoice_id": self.applied_invoice_id,
            "amount": self.amount,
            "status": self.status,
            "evidence_attachment_id": self.evidence_attachment_id,
            "reason": self.reason,
            "created_by_user": self.created_by_user,
            "branch_id": self.branch_id,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


class Variation(FoundationMixin, Base):
    """Technician-flagged extra work → supplementary quote for line approval."""

    __tablename__ = "variations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repair_order_id: Mapped[int] = mapped_column(ForeignKey("repair_order.id"), index=True)
    quote_invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # draft | sent | partially_approved | approved | rejected | cancelled
    flagged_by: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    lines: Mapped[list["VariationLine"]] = relationship(
        "VariationLine",
        back_populates="variation",
        cascade="all, delete-orphan",
    )

    def to_dict(self, *, include_lines: bool = True) -> dict:
        data = {
            "id": self.id,
            "repair_order_id": self.repair_order_id,
            "quote_invoice_id": self.quote_invoice_id,
            "status": self.status,
            "flagged_by": self.flagged_by,
            "notes": self.notes,
            "branch_id": self.branch_id,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }
        if include_lines:
            data["lines"] = [ln.to_dict() for ln in (self.lines or [])]
        return data


class VariationLine(FoundationMixin, Base):
    __tablename__ = "variation_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variation_id: Mapped[int] = mapped_column(ForeignKey("variations.id"), index=True)
    line_type: Mapped[str] = mapped_column(String(20), default="labour")
    description: Mapped[str] = mapped_column(String(255), default="")
    labour_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("labour_codes.id", ondelete="SET NULL"), nullable=True
    )
    inventory_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    approval_status: Mapped[str] = mapped_column(String(20), default="pending")

    variation: Mapped[Variation] = relationship("Variation", back_populates="lines")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "variation_id": self.variation_id,
            "line_type": self.line_type,
            "description": self.description,
            "labour_code_id": self.labour_code_id,
            "inventory_id": self.inventory_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "approval_status": self.approval_status,
        }


class QcSignoff(FoundationMixin, Base):
    """Foreman QC gate before invoice can be issued."""

    __tablename__ = "qc_signoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repair_order_id: Mapped[int] = mapped_column(ForeignKey("repair_order.id"), index=True)
    checklist_json: Mapped[str] = mapped_column(Text, default="[]")
    road_test_note: Mapped[str | None] = mapped_column(Text)
    photos_json: Mapped[str] = mapped_column(Text, default="[]")
    signed_by: Mapped[str | None] = mapped_column(String(80))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        import json

        try:
            checklist = json.loads(self.checklist_json or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            checklist = []
        try:
            photos = json.loads(self.photos_json or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            photos = []
        return {
            "id": self.id,
            "repair_order_id": self.repair_order_id,
            "checklist": checklist if isinstance(checklist, list) else [],
            "road_test_note": self.road_test_note,
            "photos": photos if isinstance(photos, list) else [],
            "signed_by": self.signed_by,
            "signed_at": _clock(self.signed_at, "%Y-%m-%d %H:%M:%S"),
            "branch_id": self.branch_id,
        }


class GatePass(FoundationMixin, Base):
    """Handover / exit: old parts, odometer, signature; starts comeback window."""

    __tablename__ = "gate_passes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repair_order_id: Mapped[int] = mapped_column(ForeignKey("repair_order.id"), index=True)
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice.id", ondelete="SET NULL"), nullable=True, index=True
    )
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    old_parts_checklist_json: Mapped[str] = mapped_column(Text, default="[]")
    exit_odometer: Mapped[str | None] = mapped_column(String(50))
    photos_json: Mapped[str] = mapped_column(Text, default="[]")
    signature_attachment_id: Mapped[int | None] = mapped_column(
        ForeignKey("attachments.id"), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    payment_gate_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(String(255))
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        import json

        try:
            checklist = json.loads(self.old_parts_checklist_json or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            checklist = []
        try:
            photos = json.loads(self.photos_json or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            photos = []
        return {
            "id": self.id,
            "repair_order_id": self.repair_order_id,
            "invoice_id": self.invoice_id,
            "visit_id": self.visit_id,
            "old_parts_checklist": checklist if isinstance(checklist, list) else [],
            "exit_odometer": self.exit_odometer,
            "photos": photos if isinstance(photos, list) else [],
            "signature_attachment_id": self.signature_attachment_id,
            "delivered_at": _clock(self.delivered_at, "%Y-%m-%d %H:%M:%S"),
            "payment_gate_override": self.payment_gate_override,
            "override_reason": self.override_reason,
            "created_by_user": self.created_by_user,
            "branch_id": self.branch_id,
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


class AppSetting(Base):
    """Key/value workshop settings (thresholds, expense heads, feature flags).

    Global rows use branch_id='' (empty) so UNIQUE(key, branch_id) works on Postgres.
    """

    __tablename__ = "app_settings"
    __table_args__ = (
        UniqueConstraint("key", "branch_id", name="uq_app_settings_key_branch"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[str] = mapped_column(Text, default="null")
    branch_id: Mapped[str] = mapped_column(String(8), default="", index=True)
    updated_by: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        import json

        try:
            parsed = json.loads(self.value) if self.value is not None else None
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = self.value
        return {
            "id": self.id,
            "key": self.key,
            "value": parsed,
            "branch_id": self.branch_id or None,
            "updated_by": self.updated_by,
            "updated_at": _clock(self.updated_at, "%Y-%m-%d %H:%M:%S"),
        }


class YardGatePass(FoundationMixin, Base):
    """Yard in/out log (document_no GP###) linked to customer/car/visit/RO.

    Distinct from pipeline ``GatePass`` (handover/exit on ``gate_passes``).
    """

    __tablename__ = "gate_pass"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    direction: Mapped[str] = mapped_column(String(10), default="in")  # in | out
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), index=True
    )
    car_id: Mapped[int | None] = mapped_column(
        ForeignKey("car.id", ondelete="SET NULL"), index=True
    )
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), index=True, nullable=True
    )
    repair_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("repair_order.id", ondelete="SET NULL"), index=True
    )
    plate_no: Mapped[str | None] = mapped_column(String(20))
    customer_name: Mapped[str | None] = mapped_column(String(255))
    purpose: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    passed_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    updated_by_user: Mapped[str | None] = mapped_column(String(80))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_no": self.document_no,
            "direction": self.direction,
            "customer_id": self.customer_id,
            "car_id": self.car_id,
            "visit_id": self.visit_id,
            "repair_order_id": self.repair_order_id,
            "plate_no": self.plate_no,
            "customer_name": self.customer_name,
            "purpose": self.purpose,
            "notes": self.notes,
            "passed_at": _clock(self.passed_at, "%Y-%m-%d %H:%M:%S"),
            "created_by_user": self.created_by_user,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


def _needs_part_number(obj: object) -> bool:
    if not isinstance(obj, Inventory) or obj.part_number:
        return False
    state = inspect(obj)
    return bool(state.transient or state.pending)


class RepairTimeEntry(FoundationMixin, Base):
    """Clock segments against a repair labour line.

    Repair time is for job cost / labour_cost only — payroll uses AttendanceRecord.
    At most one open entry per labour line (enforced in repair_execution service).
    """

    __tablename__ = "repair_time_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repair_order_id: Mapped[int] = mapped_column(ForeignKey("repair_order.id"), index=True)
    labour_id: Mapped[int] = mapped_column(ForeignKey("repair_order_labour.id"), index=True)
    worker_id: Mapped[int | None] = mapped_column(
        ForeignKey("workers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # open | closed — open means clock is running
    status: Mapped[str] = mapped_column(String(20), default="open")
    hours: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "repair_order_id": self.repair_order_id,
            "labour_id": self.labour_id,
            "worker_id": self.worker_id,
            "started_at": _clock(self.started_at, "%Y-%m-%d %H:%M:%S"),
            "ended_at": _clock(self.ended_at, "%Y-%m-%d %H:%M:%S"),
            "status": self.status,
            "hours": self.hours,
            "notes": self.notes,
            "created_by_user": self.created_by_user,
            "branch_id": self.branch_id,
        }


class RepairFault(FoundationMixin, Base):
    """Additional fault found during repair — must follow customer approval (variation)."""

    __tablename__ = "repair_faults"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repair_order_id: Mapped[int] = mapped_column(ForeignKey("repair_order.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="normal")
    # draft | awaiting_approval | approved | added | rejected | cancelled
    status: Mapped[str] = mapped_column(String(30), default="draft")
    variation_id: Mapped[int | None] = mapped_column(
        ForeignKey("variations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    photo_attachment_id: Mapped[int | None] = mapped_column(
        ForeignKey("attachments.id", ondelete="SET NULL"), nullable=True
    )
    recorded_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "repair_order_id": self.repair_order_id,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "variation_id": self.variation_id,
            "photo_attachment_id": self.photo_attachment_id,
            "recorded_by": self.recorded_by,
            "branch_id": self.branch_id,
            "created_at": _clock(self.created_at, "%Y-%m-%d %H:%M:%S"),
        }


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
        from app.document_numbers import assign_document_numbers, customer_code

        assign_document_numbers(db)
        assert customer.code == customer_code(customer.id) == "CN001"
    print("models ok")


if __name__ == "__main__":
    _demo()
