"""Up to three workshop NTNs on the branch; stamp the chosen one on each invoice.

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: Union[str, Sequence[str], None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("branches", sa.Column("ntn_options", sa.Text(), server_default="", nullable=False))
    op.execute("UPDATE branches SET ntn_options = ntn WHERE ntn <> '' AND ntn_options = ''")
    op.add_column("invoices", sa.Column("workshop_ntn", sa.String(length=15), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("invoices", "workshop_ntn")
    op.drop_column("branches", "ntn_options")
