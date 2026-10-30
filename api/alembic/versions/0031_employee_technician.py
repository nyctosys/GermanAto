"""Repair work is assigned to employees (not logins); an employee can be left out of that list.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: Union[str, Sequence[str], None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("is_technician", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.drop_constraint("repair_order_lines_technician_id_fkey", "repair_order_lines", type_="foreignkey")
    # a line assigned to a login follows that person's employee record; with none, it becomes unassigned
    op.execute("""UPDATE repair_order_lines l SET technician_id = (SELECT e.id FROM employees e WHERE e.user_id = l.technician_id)
                  WHERE l.technician_id IS NOT NULL""")
    op.create_foreign_key("repair_order_lines_technician_id_fkey", "repair_order_lines", "employees", ["technician_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("repair_order_lines_technician_id_fkey", "repair_order_lines", type_="foreignkey")
    op.execute("UPDATE repair_order_lines l SET technician_id = (SELECT e.user_id FROM employees e WHERE e.id = l.technician_id)")
    op.create_foreign_key("repair_order_lines_technician_id_fkey", "repair_order_lines", "users", ["technician_id"], ["id"])
    op.drop_column("employees", "is_technician")
