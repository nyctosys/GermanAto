"""VIN and chassis number are one field

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("car_vin_format", "cars", type_="check")
    op.alter_column("cars", "vin", type_=sa.String(30), existing_nullable=False)
    op.execute("UPDATE cars SET vin = upper(regexp_replace(chassis_no, '\\s', '', 'g')) WHERE vin = '' AND chassis_no <> ''")
    op.drop_column("cars", "chassis_no")
    op.create_check_constraint("car_vin_format", "cars", "vin = '' OR vin ~ '^[A-Z0-9-]{5,30}$'")


def downgrade() -> None:
    op.drop_constraint("car_vin_format", "cars", type_="check")
    op.add_column("cars", sa.Column("chassis_no", sa.String(40), nullable=False, server_default=""))
    op.execute("UPDATE cars SET chassis_no = vin, vin = '' WHERE vin !~ '^[A-HJ-NPR-Z0-9]{17}$'")
    op.alter_column("cars", "vin", type_=sa.String(17), existing_nullable=False)
    op.create_check_constraint("car_vin_format", "cars", "vin = '' OR vin ~ '^[A-HJ-NPR-Z0-9]{17}$'")
