"""Branch identifiers: 8-char lowercase hex. Default workshop branch is seeded."""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session, Query

DEFAULT_BRANCH_ID = "a1b2c3d4"
DEFAULT_BRANCH_NAME = "Main Workshop"


def new_branch_id() -> str:
    return secrets.token_hex(4)


def ensure_default_branch(db: Session) -> str:
    from app.models import Branch

    row = db.get(Branch, DEFAULT_BRANCH_ID)
    if row is None:
        db.add(
            Branch(
                id=DEFAULT_BRANCH_ID,
                name=DEFAULT_BRANCH_NAME,
                is_default=True,
            )
        )
        db.flush()
    return DEFAULT_BRANCH_ID


def for_branch(query: Query, model, branch_id: str | None):
    """Scope a SQLAlchemy query to one branch when the model has branch_id."""
    if branch_id is None or not hasattr(model, "branch_id"):
        return query
    return query.filter(model.branch_id == branch_id)
