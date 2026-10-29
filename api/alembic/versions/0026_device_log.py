"""Attendance device activity log (for debugging a terminal that does not seem to work).

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0026"
down_revision: Union[str, Sequence[str], None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('device_logs',
    sa.Column('device_id', sa.Uuid(), nullable=False),
    sa.Column('event', sa.String(length=12), nullable=False),
    sa.Column('detail', sa.String(length=300), nullable=False),
    sa.Column('branch_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ),
    sa.ForeignKeyConstraint(['device_id'], ['attendance_devices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_device_logs_branch_id'), 'device_logs', ['branch_id'], unique=False)
    op.create_index('ix_device_log_device_time', 'device_logs', ['device_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_device_log_device_time', table_name='device_logs')
    op.drop_index(op.f('ix_device_logs_branch_id'), table_name='device_logs')
    op.drop_table('device_logs')
