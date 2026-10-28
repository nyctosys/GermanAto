import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, BranchScoped, Entity, uuid7, utcnow


class Branch(Entity):
    """A workshop. Its own settings live here rather than in a key/value table."""

    __tablename__ = "branches"
    __table_args__ = (
        CheckConstraint("code ~ '^[0-9A-F]{4}$'", name="branch_code_hex"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="branch_tax_rate_range"),
    )

    code: Mapped[str] = mapped_column(String(4), unique=True)  # appears in document numbers
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(300), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(120), default="")
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("17.00"))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Karachi")
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Role(Entity):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(60), unique=True)
    description: Mapped[str] = mapped_column(String(200), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # holds every permission

    permissions: Mapped[list["RolePermission"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class RolePermission(Entity):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission"),)

    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    permission: Mapped[str] = mapped_column(String(60))


class User(Entity):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("username = lower(username)", name="username_lowercase"),)
    __audit_exclude__ = {"password_hash", "failed_logins", "locked_until", "last_login_at"}

    username: Mapped[str] = mapped_column(String(32), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(120), unique=True)
    phone: Mapped[str] = mapped_column(String(20), default="")
    password_hash: Mapped[str] = mapped_column(String(200))
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role] = relationship(lazy="joined")
    branches: Mapped[list["UserBranch"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class UserBranch(Entity):
    __tablename__ = "user_branches"
    __table_args__ = (UniqueConstraint("user_id", "branch_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))


class UserSession(Base):
    """Server-side login session. The cookie holds a random token; only its
    hash is stored, and logging out deletes the row. Local to each server,
    never synced."""

    __tablename__ = "user_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str] = mapped_column(String(45), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")


class AuditLog(Base):
    """Append-only. Written by the flush hook in app.events for every change,
    and directly for actions that change nothing (login, print, export)."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now(), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))  # create / update / delete / login / login_failed / ...
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    changes: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip: Mapped[str] = mapped_column(String(45), default="")


class Attachment(BranchScoped):
    """A proof file (receipt photo, PDF, signature). Stored once per content
    hash; the row links it to the record it proves."""

    __tablename__ = "attachments"
    __table_args__ = (CheckConstraint("size > 0", name="attachment_size_positive"),)

    sha256: Mapped[str] = mapped_column(String(64), index=True)
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(BigInteger)
    original_name: Mapped[str] = mapped_column(String(255))
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    note: Mapped[str] = mapped_column(Text, default="")


class SyncOutbox(Base):
    """Every change, in order, waiting for the sync worker (spec §6). Written
    in the same transaction as the change itself."""

    __tablename__ = "sync_outbox"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(60))
    row_id: Mapped[uuid.UUID]
    op: Mapped[str] = mapped_column(String(10))  # upsert / delete
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


# --- Numbering ------------------------------------------------------------

class NumberSequence(Base):
    """Next human number per branch and document kind (CUS-A1F3-000001).
    Not synced: each branch server is the only writer of its own numbers."""

    __tablename__ = "number_sequences"

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_value: Mapped[int] = mapped_column(BigInteger, default=0)


# --- Customers & cars (shared by every branch) -----------------------------

class Customer(Entity):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("kind IN ('individual', 'company')", name="customer_kind"),
        Index("ix_customers_phone", "phone"),
    )

    number: Mapped[str] = mapped_column(String(24), unique=True)
    kind: Mapped[str] = mapped_column(String(12), default="individual")
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    phone_alt: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(120), default="")
    cnic: Mapped[str] = mapped_column(String(15), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    whatsapp_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Car(Entity):
    __tablename__ = "cars"
    __table_args__ = (
        CheckConstraint("fuel IN ('petrol', 'diesel', 'hybrid', 'ev', 'cng', 'other')", name="car_fuel"),
        CheckConstraint("vin = '' OR vin ~ '^[A-Z0-9-]{5,30}$'", name="car_vin_format"),
        # One car per plate and per VIN; blank values don't count.
        Index("uq_cars_plate", "plate_norm", unique=True, postgresql_where=text("plate_norm <> ''")),
        Index("uq_cars_vin", "vin", unique=True, postgresql_where=text("vin <> ''")),
    )

    plate: Mapped[str] = mapped_column(String(20), default="")      # as written: LEA-21-1234
    plate_norm: Mapped[str] = mapped_column(String(20), default="")  # for matching: LEA211234
    vin: Mapped[str] = mapped_column(String(30), default="")  # VIN or chassis number: the same thing
    engine_no: Mapped[str] = mapped_column(String(40), default="")
    make: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(60), default="")
    year: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(40), default="")
    fuel: Mapped[str] = mapped_column(String(10), default="petrol")
    odometer_km: Mapped[int | None] = mapped_column(Integer)  # last reading seen
    notes: Mapped[str] = mapped_column(Text, default="")


class CarOwnership(Entity):
    """Who owned a car and when. The open row (until is null) is the current
    owner; a transfer closes it and opens the next one."""

    __tablename__ = "car_ownerships"
    __table_args__ = (
        Index("uq_car_current_owner", "car_id", unique=True, postgresql_where=text("until IS NULL")),
        CheckConstraint("until IS NULL OR until >= since", name="ownership_dates"),
    )

    car_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cars.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    since: Mapped[date] = mapped_column(Date)
    until: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(300), default="")
    odometer_km: Mapped[int | None] = mapped_column(Integer)


# --- Catalogue: labour codes and inventory (per branch) --------------------

class LabourCode(BranchScoped):
    __tablename__ = "labour_codes"
    __table_args__ = (
        UniqueConstraint("branch_id", "code"),
        CheckConstraint("code ~ '^[A-Z0-9][A-Z0-9-]{1,23}$'", name="labour_code_format"),
    )

    code: Mapped[str] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Item(BranchScoped):
    """A stock item. Quantity on hand is never stored: it is the sum of its
    stock movements (spec D4)."""

    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("sale_price >= 0", name="item_sale_price"),
        CheckConstraint("avg_cost >= 0", name="item_avg_cost"),
        CheckConstraint("reorder_level >= 0 AND reorder_qty >= 0", name="item_reorder"),
    )

    number: Mapped[str] = mapped_column(String(24), unique=True)  # internal, e.g. ITM-A1F3-000042
    name: Mapped[str] = mapped_column(String(160))
    brand: Mapped[str] = mapped_column(String(60), default="")
    category: Mapped[str] = mapped_column(String(60), default="")
    unit: Mapped[str] = mapped_column(String(12), default="pcs")
    fitment: Mapped[str] = mapped_column(String(200), default="")  # e.g. "BMW 5 Series F10 2010-2016"
    location: Mapped[str] = mapped_column(String(60), default="")  # bin / shelf
    sale_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0"))  # from goods received
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))
    reorder_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    codes: Mapped[list["ItemCode"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="ItemCode.created_at")


class ItemCode(BranchScoped):
    """A barcode or manufacturer part number. Matching uses the normalised
    form, so "11-42 7.583" and "1142 7583" are the same part."""

    __tablename__ = "item_codes"
    __table_args__ = (
        UniqueConstraint("branch_id", "code_norm"),
        CheckConstraint("kind IN ('barcode', 'mpn')", name="item_code_kind"),
        CheckConstraint("code_norm ~ '^[A-Z0-9]{3,40}$'", name="item_code_norm_format"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    code: Mapped[str] = mapped_column(String(60))
    code_norm: Mapped[str] = mapped_column(String(40))


class StockMovement(BranchScoped):
    """Append-only. Every unit in or out of stock, with its cost. Corrections
    are new movements, never edits (spec D4, D5)."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("qty <> 0", name="movement_qty_nonzero"),
        CheckConstraint("unit_cost >= 0", name="movement_cost"),
        CheckConstraint("kind IN ('opening', 'adjustment', 'grn', 'issue', 'return', 'sale', 'credit')", name="movement_kind"),
        Index("ix_stock_item_created", "item_id", "created_at"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"))
    kind: Mapped[str] = mapped_column(String(12))
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3))          # + in, - out
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4))    # cost per unit at the time
    reason: Mapped[str] = mapped_column(String(300), default="")
    source_type: Mapped[str | None] = mapped_column(String(40))   # grn / repair_order / invoice ...
    source_id: Mapped[uuid.UUID | None] = mapped_column(index=True)


# --- Workshop: visits and inspections (spec §2, §2.4) -----------------------

class Visit(BranchScoped):
    """One stay of a car in the workshop, from check-in to gate pass. Every
    workshop document belongs to a visit."""

    __tablename__ = "visits"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'closed', 'cancelled')", name="visit_status"),
        CheckConstraint("kind IN ('workshop', 'pre_purchase')", name="visit_kind"),
        CheckConstraint("fuel_eighths IS NULL OR fuel_eighths BETWEEN 0 AND 8", name="visit_fuel"),
        CheckConstraint("odometer_out IS NULL OR odometer_in IS NULL OR odometer_out >= odometer_in", name="visit_odometer"),
        CheckConstraint("kind = 'workshop' OR buyer_id IS NOT NULL", name="visit_pre_purchase_buyer"),
        # A car can be in the workshop only once at a time.
        Index("uq_visit_open_car", "car_id", unique=True, postgresql_where=text("status = 'open'")),
    )

    number: Mapped[str] = mapped_column(String(24), unique=True)
    kind: Mapped[str] = mapped_column(String(14), default="workshop")
    status: Mapped[str] = mapped_column(String(10), default="open")
    car_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cars.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)  # owner at check-in
    # Pre-purchase: the person thinking of buying. The seller is the car's owner (customer_id).
    buyer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"), index=True)
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    odometer_in: Mapped[int | None] = mapped_column(Integer)
    fuel_eighths: Mapped[int | None] = mapped_column(Integer)
    complaint: Mapped[str] = mapped_column(Text, default="")
    items_left: Mapped[str] = mapped_column(Text, default="")      # valuables left in the car
    condition_notes: Mapped[str] = mapped_column(Text, default="")
    signature_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attachments.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    odometer_out: Mapped[int | None] = mapped_column(Integer)
    close_note: Mapped[str] = mapped_column(Text, default="")       # cancel reason, or credit release reason
    released_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))  # gate pass
    handed_to: Mapped[str] = mapped_column(String(120), default="")                # who collected the car
    credit_released_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    credit_reason: Mapped[str] = mapped_column(Text, default="")


class Inspection(BranchScoped):
    """The vehicle inspection report. Answers are kept as validated JSON
    against app.inspection_template at `template_version`."""

    __tablename__ = "inspections"
    __table_args__ = (
        CheckConstraint("kind IN ('workshop', 'delivery', 'pre_purchase')", name="inspection_kind"),
        CheckConstraint("status IN ('draft', 'signed')", name="inspection_status"),
    )

    number: Mapped[str] = mapped_column(String(24), unique=True)
    kind: Mapped[str] = mapped_column(String(14))
    status: Mapped[str] = mapped_column(String(8), default="draft")
    visit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visits.id"), index=True)
    car_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cars.id"), index=True)
    template_version: Mapped[int] = mapped_column(Integer)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("inspections.id"))  # a correction of a signed one
    data: Mapped[dict] = mapped_column(JSONB, default=dict)  # every section's answers (see routers/workshop.py)
    inspector_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inspector_signature_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attachments.id"))
    customer_signature_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attachments.id"))


# --- estimates: job card, quotation, advance (spec §2, §2.2) --------------------------------

LINE_TARGET = ("(kind = 'labour' AND labour_code_id IS NOT NULL AND item_id IS NULL) OR "
               "(kind = 'part' AND item_id IS NOT NULL AND labour_code_id IS NULL)")


class JobCard(BranchScoped):
    """The rough work list for a visit: labour codes and stock items only, no prices."""

    __tablename__ = "job_cards"

    number: Mapped[str] = mapped_column(String(24), unique=True)
    visit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visits.id"), unique=True)  # one per visit
    notes: Mapped[str] = mapped_column(Text, default="")

    lines: Mapped[list["JobCardLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin",
                                                      order_by="JobCardLine.position")


class JobCardLine(Entity):
    __tablename__ = "job_card_lines"
    __table_args__ = (
        CheckConstraint("kind IN ('labour', 'part')", name="job_line_kind"),
        CheckConstraint(LINE_TARGET, name="job_line_target"),
        CheckConstraint("qty > 0", name="job_line_qty"),
    )

    job_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_cards.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(8))
    labour_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("labour_codes.id"))
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("1"))
    note: Mapped[str] = mapped_column(String(300), default="")


class Quotation(BranchScoped):
    """What the customer agrees to. Each revision is a new row with the same
    number; only one revision per visit is current (not 'revised')."""

    __tablename__ = "quotations"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'sent', 'approved', 'rejected', 'revised', 'converted')", name="quotation_status"),
        CheckConstraint("approval_method IS NULL OR approval_method IN ('in_person', 'whatsapp', 'phone')", name="quotation_method"),
        CheckConstraint("status <> 'approved' OR (approved_at IS NOT NULL AND (approval_proof_id IS NOT NULL OR no_proof_reason <> ''))",
                        name="quotation_approval_proof"),
        CheckConstraint("discount >= 0", name="quotation_discount"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="quotation_tax_rate"),
        UniqueConstraint("number", "revision"),
        Index("uq_quotation_current", "visit_id", unique=True, postgresql_where=text("status <> 'revised'")),
    )

    number: Mapped[str] = mapped_column(String(24))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotations.id"))
    visit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visits.id"), index=True)
    job_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_cards.id"))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    include_tax: Mapped[bool] = mapped_column(Boolean, default=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    valid_until: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approval_method: Mapped[str | None] = mapped_column(String(10))
    approval_note: Mapped[str] = mapped_column(Text, default="")
    approval_proof_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attachments.id"))
    no_proof_reason: Mapped[str] = mapped_column(Text, default="")
    rejected_reason: Mapped[str] = mapped_column(Text, default="")

    lines: Mapped[list["QuotationLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin",
                                                        order_by="QuotationLine.position")


class QuotationLine(Entity):
    __tablename__ = "quotation_lines"
    __table_args__ = (
        CheckConstraint("kind IN ('labour', 'part')", name="quote_line_kind"),
        CheckConstraint(LINE_TARGET, name="quote_line_target"),
        CheckConstraint("qty > 0", name="quote_line_qty"),
        CheckConstraint("unit_price >= 0", name="quote_line_price"),
    )

    quotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotations.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(8))
    labour_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("labour_codes.id"))
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id"))
    description: Mapped[str] = mapped_column(String(200))  # the code's or item's name when quoted
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    declined: Mapped[bool] = mapped_column(Boolean, default=False)  # partial approval


class Payment(BranchScoped):
    """Money in. An advance is held for the customer (a liability) until an
    invoice uses it. Never edited: a mistake is voided with a reason."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("kind IN ('advance', 'invoice', 'other')", name="payment_kind"),
        CheckConstraint("status IN ('posted', 'voided')", name="payment_status"),
        CheckConstraint("account IN ('cash', 'bank', 'wallet')", name="payment_account"),
        CheckConstraint("amount > 0", name="payment_amount"),
        CheckConstraint("proof_id IS NOT NULL OR no_proof_reason <> ''", name="payment_proof"),
    )

    number: Mapped[str] = mapped_column(String(24), unique=True)
    kind: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(8), default="posted")
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"), index=True)  # None: walk-in sale
    visit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visits.id"), index=True)
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotations.id"))
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"), index=True)  # set when applied
    account: Mapped[str] = mapped_column(String(8))
    reference: Mapped[str] = mapped_column(String(60), default="")  # cheque no., transaction id
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    proof_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attachments.id"))
    no_proof_reason: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    received_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    void_reason: Mapped[str] = mapped_column(Text, default="")


# --- repair order (spec §2, §2.3) ------------------------------------------------------------

RO_STAGES = ("received", "diagnosis", "awaiting_approval", "in_repair", "testing", "ready", "delivered")


class RepairOrder(BranchScoped):
    """What was actually done. Made from an approved quotation; parts are issued
    from stock here, and every event lands in its activity trail."""

    __tablename__ = "repair_orders"
    __table_args__ = (
        CheckConstraint(f"status IN {RO_STAGES + ('on_hold',)}", name="ro_status"),
        CheckConstraint("status <> 'on_hold' OR held_from IS NOT NULL", name="ro_hold_from"),
    )

    number: Mapped[str] = mapped_column(String(24), unique=True)
    visit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visits.id"), unique=True)  # one per visit
    quotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotations.id"))
    status: Mapped[str] = mapped_column(String(18), default="received")
    held_from: Mapped[str | None] = mapped_column(String(18))  # the stage to resume to

    lines: Mapped[list["RepairOrderLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin",
                                                          order_by="RepairOrderLine.position")


class RepairOrderLine(Entity):
    __tablename__ = "repair_order_lines"
    __table_args__ = (
        CheckConstraint("kind IN ('labour', 'part')", name="ro_line_kind"),
        CheckConstraint(LINE_TARGET, name="ro_line_target"),
        CheckConstraint("qty > 0", name="ro_line_qty"),
        CheckConstraint("unit_price >= 0", name="ro_line_price"),
        CheckConstraint("state IN ('pending', 'done', 'not_done')", name="ro_line_state"),
        CheckConstraint("issued_qty >= 0 AND (kind = 'part' OR issued_qty = 0)", name="ro_line_issued"),
    )

    repair_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repair_orders.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(8))
    labour_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("labour_codes.id"))
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id"))
    description: Mapped[str] = mapped_column(String(200))
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # the agreed price
    in_quote: Mapped[bool] = mapped_column(Boolean, default=True)  # False: extra work added after approval
    state: Mapped[str] = mapped_column(String(8), default="pending")
    technician_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    issued_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))  # net of returns


class RepairOrderActivity(BranchScoped):
    """Append-only timeline. Internal unless marked customer-visible (§2.3)."""

    __tablename__ = "repair_order_activity"
    __table_args__ = (
        CheckConstraint("kind IN ('status', 'finding', 'note', 'parts', 'customer_update', 'line')", name="ro_activity_kind"),
    )

    repair_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repair_orders.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text, default="")
    from_status: Mapped[str | None] = mapped_column(String(18))
    to_status: Mapped[str | None] = mapped_column(String(18))
    line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("repair_order_lines.id", ondelete="SET NULL"))
    customer_visible: Mapped[bool] = mapped_column(Boolean, default=False)


# --- invoices (spec §2, §2.1) -----------------------------------------------------------------

class Invoice(BranchScoped):
    """The final bill. Workshop invoices bill what the repair order did; counter
    sales sell parts over the counter. Issued invoices are locked."""

    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("kind IN ('workshop', 'counter_sale')", name="invoice_kind"),
        CheckConstraint("status IN ('draft', 'issued', 'void')", name="invoice_status"),
        CheckConstraint("kind = 'counter_sale' OR (visit_id IS NOT NULL AND repair_order_id IS NOT NULL)", name="invoice_workshop_links"),
        CheckConstraint("status <> 'issued' OR issued_at IS NOT NULL", name="invoice_issued_at"),
        CheckConstraint("discount >= 0", name="invoice_discount"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="invoice_tax_rate"),
        # One live workshop invoice per visit (spec §2 rules).
        Index("uq_invoice_visit", "visit_id", unique=True, postgresql_where=text("kind = 'workshop' AND status <> 'void'")),
    )

    number: Mapped[str] = mapped_column(String(24), unique=True)
    kind: Mapped[str] = mapped_column(String(14))
    status: Mapped[str] = mapped_column(String(8), default="draft")
    visit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visits.id"), index=True)
    repair_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("repair_orders.id"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"), index=True)  # None: walk-in
    car_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cars.id"), index=True)
    walk_in_name: Mapped[str] = mapped_column(String(120), default="")
    walk_in_phone: Mapped[str] = mapped_column(String(16), default="")
    include_tax: Mapped[bool] = mapped_column(Boolean, default=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    notes: Mapped[str] = mapped_column(Text, default="")
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["InvoiceLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin",
                                                      order_by="InvoiceLine.position")


class InvoiceLine(Entity):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("kind IN ('labour', 'part')", name="invoice_line_kind"),
        CheckConstraint(LINE_TARGET, name="invoice_line_target"),
        CheckConstraint("qty > 0", name="invoice_line_qty"),
        CheckConstraint("unit_price >= 0", name="invoice_line_price"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(8))
    labour_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("labour_codes.id"))
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id"))
    repair_order_line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("repair_order_lines.id"))
    description: Mapped[str] = mapped_column(String(200))
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    in_quote: Mapped[bool] = mapped_column(Boolean, default=True)
