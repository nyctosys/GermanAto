"""Extra work on a repair order no longer needs customer-agreement proof.

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-05

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0034"
down_revision: Union[str, Sequence[str], None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ro_line_extra_approved", "repair_order_lines", type_="check")


def downgrade() -> None:
    op.create_check_constraint(
        "ro_line_extra_approved",
        "repair_order_lines",
        "in_quote OR (approval_method IS NOT NULL AND (approval_proof_id IS NOT NULL OR approval_reason <> ''))",
    )
