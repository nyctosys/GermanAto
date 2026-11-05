"""Allow more than one signed count per account per day (post-closing recounts).

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0035"
down_revision: Union[str, Sequence[str], None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cash_closes", sa.Column("sequence", sa.Integer(), server_default="1", nullable=False))
    op.drop_constraint("cash_closes_branch_id_account_close_date_key", "cash_closes", type_="unique")
    op.create_unique_constraint("uq_cash_close_day_seq", "cash_closes", ["branch_id", "account", "close_date", "sequence"])


def downgrade() -> None:
    op.drop_constraint("uq_cash_close_day_seq", "cash_closes", type_="unique")
    op.create_unique_constraint("cash_closes_branch_id_account_close_date_key", "cash_closes", ["branch_id", "account", "close_date"])
    op.drop_column("cash_closes", "sequence")
