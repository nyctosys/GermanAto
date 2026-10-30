"""A pre-purchase inspection is billed with its own invoice kind: one fee line, no repair order behind it.

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-31

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0032"
down_revision: Union[str, Sequence[str], None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("invoice_kind", "invoices", type_="check")
    op.drop_constraint("invoice_workshop_links", "invoices", type_="check")
    op.drop_index("uq_invoice_visit", table_name="invoices")
    op.create_check_constraint("invoice_kind", "invoices", "kind IN ('workshop', 'counter_sale', 'inspection')")
    op.create_check_constraint("invoice_workshop_links", "invoices",
                               "kind = 'counter_sale' OR (visit_id IS NOT NULL AND (repair_order_id IS NOT NULL OR kind = 'inspection'))")
    op.create_index("uq_invoice_visit", "invoices", ["visit_id"], unique=True,
                    postgresql_where="kind IN ('workshop', 'inspection') AND status <> 'void'")


def downgrade() -> None:
    op.drop_index("uq_invoice_visit", table_name="invoices")
    op.drop_constraint("invoice_workshop_links", "invoices", type_="check")
    op.drop_constraint("invoice_kind", "invoices", type_="check")
    op.create_check_constraint("invoice_kind", "invoices", "kind IN ('workshop', 'counter_sale')")
    op.create_check_constraint("invoice_workshop_links", "invoices", "kind = 'counter_sale' OR (visit_id IS NOT NULL AND repair_order_id IS NOT NULL)")
    op.create_index("uq_invoice_visit", "invoices", ["visit_id"], unique=True, postgresql_where="kind = 'workshop' AND status <> 'void'")
