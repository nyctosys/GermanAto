"""Simplify repair order stages to received → in_repair → testing → ready → delivered.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-29

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0024"
down_revision: Union[str, Sequence[str], None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Map retired stages onto the shop-friendly set before tightening the check.
    op.execute("UPDATE repair_orders SET status = 'received' WHERE status = 'diagnosis'")
    op.execute("UPDATE repair_orders SET status = 'in_repair' WHERE status = 'awaiting_approval'")
    op.execute("UPDATE repair_orders SET held_from = 'received' WHERE held_from = 'diagnosis'")
    op.execute("UPDATE repair_orders SET held_from = 'in_repair' WHERE held_from = 'awaiting_approval'")
    op.execute("ALTER TABLE repair_orders DROP CONSTRAINT IF EXISTS ro_status")
    op.execute(
        "ALTER TABLE repair_orders ADD CONSTRAINT ro_status "
        "CHECK (status IN ('received', 'in_repair', 'testing', 'ready', 'delivered', 'on_hold'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE repair_orders DROP CONSTRAINT IF EXISTS ro_status")
    op.execute(
        "ALTER TABLE repair_orders ADD CONSTRAINT ro_status "
        "CHECK (status IN ('received', 'diagnosis', 'awaiting_approval', 'in_repair', "
        "'testing', 'ready', 'delivered', 'on_hold'))"
    )
