"""Company customers can carry an NTN (National Tax Number).

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, Sequence[str], None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("ntn", sa.String(length=15), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("customers", "ntn")
