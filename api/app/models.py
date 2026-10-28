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
        CheckConstraint("vin = '' OR vin ~ '^[A-HJ-NPR-Z0-9]{17}$'", name="car_vin_format"),
        # One car per plate and per VIN; blank values don't count.
        Index("uq_cars_plate", "plate_norm", unique=True, postgresql_where=text("plate_norm <> ''")),
        Index("uq_cars_vin", "vin", unique=True, postgresql_where=text("vin <> ''")),
    )

    plate: Mapped[str] = mapped_column(String(20), default="")      # as written: LEA-21-1234
    plate_norm: Mapped[str] = mapped_column(String(20), default="")  # for matching: LEA211234
    vin: Mapped[str] = mapped_column(String(17), default="")
    chassis_no: Mapped[str] = mapped_column(String(40), default="")
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
