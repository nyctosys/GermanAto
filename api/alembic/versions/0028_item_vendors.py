"""Which vendors supply an item (an item can have several).

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0028"
down_revision: Union[str, Sequence[str], None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('item_vendors',
    sa.Column('item_id', sa.Uuid(), nullable=False),
    sa.Column('vendor_id', sa.Uuid(), nullable=False),
    sa.Column('unit_cost', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('branch_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    sa.CheckConstraint('unit_cost IS NULL OR unit_cost >= 0', name='item_vendor_cost'),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
    sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('item_id', 'vendor_id')
    )
    op.create_index(op.f('ix_item_vendors_branch_id'), 'item_vendors', ['branch_id'], unique=False)
    op.create_index(op.f('ix_item_vendors_vendor_id'), 'item_vendors', ['vendor_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_item_vendors_vendor_id'), table_name='item_vendors')
    op.drop_index(op.f('ix_item_vendors_branch_id'), table_name='item_vendors')
    op.drop_table('item_vendors')
