"""Items fit several cars now (a pick-list of names joined by semicolons), so the column is longer.

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, Sequence[str], None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("items", "fitment", existing_type=sa.String(200), type_=sa.String(600), existing_nullable=False)


def downgrade() -> None:
    op.alter_column("items", "fitment", existing_type=sa.String(600), type_=sa.String(200), existing_nullable=False)
