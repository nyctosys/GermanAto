"""Partly refund a held advance: remember how much has gone back.

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0027"
down_revision: Union[str, Sequence[str], None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payments', sa.Column('refunded_amount', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False))
    op.execute("UPDATE payments SET refunded_amount = amount WHERE refunded")


def downgrade() -> None:
    op.drop_column('payments', 'refunded_amount')
