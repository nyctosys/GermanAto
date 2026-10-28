import os
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def set_actor(db, user_id=None, branch_id=None, ip=None) -> None:
    """Record who is acting on this DB session. The flush hooks in app.events
    stamp created_by/updated_by/branch_id and write audit rows from it.

    Kept on the session rather than in a ContextVar: FastAPI runs sync
    dependencies in worker threads, so a ContextVar set there never reaches
    the endpoint. The session object is shared by both."""
    for key, value in (("user_id", user_id), ("branch_id", branch_id), ("ip", ip)):
        if value is not None:
            db.info[key] = value


def uuid7() -> uuid.UUID:
    """Time-ordered UUID (RFC 9562 v7): ids sort by creation time and can be
    minted offline on any branch server without colliding."""
    ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | (rand >> 68 & 0xFFF) << 64 | 0b10 << 62 | rand & ((1 << 62) - 1)
    return uuid.UUID(int=value)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Entity(Base):
    """Columns every synced table carries (spec §4)."""

    __abstract__ = True
    __synced__ = True  # picked up by the audit/outbox hook

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now())
    created_by: Mapped[uuid.UUID | None]  # stamped by app.events
    updated_by: Mapped[uuid.UUID | None]
    version: Mapped[int] = mapped_column(Integer, server_default="1")

    # Optimistic locking: a stale edit (two tabs, or a sync replay) fails
    # instead of silently overwriting the newer row.
    @declared_attr.directive
    def __mapper_args__(cls):
        return {"version_id_col": cls.__table__.c.version}


class BranchScoped(Entity):
    __abstract__ = True

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id"), index=True)  # stamped by app.events


def get_db():
    with SessionLocal() as db:
        yield db


def self_check():
    a, b = uuid7(), uuid7()
    assert a.version == 7 and a.variant == uuid.RFC_4122
    assert a.int >> 80 <= b.int >> 80  # timestamp prefix never goes backwards


if __name__ == "__main__":
    self_check()
    print("ok", uuid7())
