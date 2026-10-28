import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func,
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
