"""add order_number sequence, eta split, users.role

Revision ID: 3e071ffdf90f
Revises: 596085d8e353
Create Date: 2026-07-25 13:02:09.378765

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e071ffdf90f'
down_revision: Union[str, None] = '596085d8e353'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate can't create the sequence the model's server_default
    # refers to (nextval('orders_order_number_seq')) — hand-added, same
    # two-step pattern as the order_statuses seed migration.
    op.execute("CREATE SEQUENCE IF NOT EXISTS orders_order_number_seq")
    op.add_column('orders', sa.Column('order_number', sa.Integer(), server_default=sa.text("nextval('orders_order_number_seq')"), nullable=False))
    op.add_column('orders', sa.Column('eta_start', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('eta_end', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(None, 'orders', ['order_number'])
    op.drop_column('orders', 'eta')
    # server_default backfills existing rows; model keeps a Python-side
    # default for new inserts, matching the pattern already used elsewhere.
    op.add_column('users', sa.Column('role', sa.String(length=20), server_default='customer', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'role')
    op.add_column('orders', sa.Column('eta', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'orders', type_='unique')
    op.drop_column('orders', 'eta_end')
    op.drop_column('orders', 'eta_start')
    op.drop_column('orders', 'order_number')
    op.execute("DROP SEQUENCE IF EXISTS orders_order_number_seq")
