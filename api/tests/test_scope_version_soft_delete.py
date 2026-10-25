"""Foundation: branch assign, soft delete, optimistic locking (SQLite in-memory)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import current_branch_id, current_reason, current_user_obj
from app.foundation.hooks import install_foundation_hooks
from app.foundation.scope import assign_branch, scoped_query
from app.foundation.soft_delete import soft_delete
from app.foundation.versioning import VersionConflict, bump_version, check_version
from app.models import Expense, User


@pytest.fixture()
def db():
    install_foundation_hooks()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    # Seed branch-scoped context
    t1 = current_branch_id.set(DEFAULT_BRANCH_ID)
    t2 = current_reason.set("test reason")
    t3 = current_user_obj.set(None)
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        current_branch_id.reset(t1)
        current_reason.reset(t2)
        current_user_obj.reset(t3)
        engine.dispose()


def test_assign_branch_and_scoped_query(db: Session):
    exp = Expense(
        date=__import__("datetime").date.today(),
        category="misc",
        description="tea",
        amount=10.0,
    )
    assign_branch(exp)
    assert exp.branch_id == DEFAULT_BRANCH_ID
    db.add(exp)
    db.commit()

    other = Expense(
        date=__import__("datetime").date.today(),
        category="misc",
        description="other-branch",
        amount=5.0,
        branch_id="deadbeef",
    )
    db.add(other)
    db.commit()

    rows = scoped_query(db, Expense, DEFAULT_BRANCH_ID).all()
    assert all(r.branch_id == DEFAULT_BRANCH_ID for r in rows)
    assert all(r.description != "other-branch" for r in rows)


def test_soft_delete_excludes_from_scoped_query(db: Session):
    exp = Expense(
        date=__import__("datetime").date.today(),
        category="misc",
        description="gone",
        amount=1.0,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(exp)
    db.commit()
    soft_delete(exp, by="tester")
    db.commit()

    assert scoped_query(db, Expense).filter_by(id=exp.id).first() is None
    assert exp.deleted_at is not None


def test_session_delete_soft_deletes(db: Session):
    exp = Expense(
        date=__import__("datetime").date.today(),
        category="misc",
        description="soft-via-delete",
        amount=2.0,
        branch_id=DEFAULT_BRANCH_ID,
    )
    db.add(exp)
    db.commit()
    db.delete(exp)
    db.commit()
    assert exp.deleted_at is not None
    # Row still physically present
    raw = db.get(Expense, exp.id)
    assert raw is not None
    assert raw.deleted_at is not None


def test_optimistic_lock_conflict(db: Session):
    exp = Expense(
        date=__import__("datetime").date.today(),
        category="misc",
        description="ver",
        amount=1.0,
        branch_id=DEFAULT_BRANCH_ID,
        version=1,
    )
    db.add(exp)
    db.commit()
    with pytest.raises(VersionConflict):
        check_version(exp, 99)
    check_version(exp, 1)
    bump_version(exp)
    assert exp.version == 2
