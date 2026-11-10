"""Workshop NTN on the branch, and buyer NTN on each invoice.

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: Union[str, Sequence[str], None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("branches", sa.Column("ntn", sa.String(length=15), server_default="", nullable=False))
    op.add_column("invoices", sa.Column("ntn", sa.String(length=15), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("invoices", "ntn")
    op.drop_column("branches", "ntn")
