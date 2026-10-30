"""Team-managed pick-lists (brands, categories, car makes, labour categories).

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0029"
down_revision: Union[str, Sequence[str], None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('pick_list_entries',
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('key', sa.String(length=60), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('branch_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('branch_id', 'kind', 'key')
    )
    op.create_index(op.f('ix_pick_list_entries_branch_id'), 'pick_list_entries', ['branch_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pick_list_entries_branch_id'), table_name='pick_list_entries')
    op.drop_table('pick_list_entries')
