"""Several weekly days off per employee, and a 'present' day mark (8 hours).

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0025"
down_revision: Union[str, Sequence[str], None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE employees ADD COLUMN days_off integer[] NOT NULL DEFAULT '{6}'")
    op.execute("UPDATE employees SET days_off = ARRAY[weekly_off]")
    op.execute("ALTER TABLE day_marks DROP CONSTRAINT IF EXISTS mark_kind")
    op.execute("ALTER TABLE day_marks ADD CONSTRAINT mark_kind CHECK (kind IN ('paid_leave', 'unpaid_leave', 'present'))")
    op.execute("ALTER TABLE day_marks ALTER COLUMN kind TYPE varchar(14)")


def downgrade() -> None:
    op.execute("DELETE FROM day_marks WHERE kind = 'present'")
    op.execute("ALTER TABLE day_marks DROP CONSTRAINT IF EXISTS mark_kind")
    op.execute("ALTER TABLE day_marks ADD CONSTRAINT mark_kind CHECK (kind IN ('paid_leave', 'unpaid_leave'))")
    op.execute("ALTER TABLE employees DROP COLUMN days_off")
