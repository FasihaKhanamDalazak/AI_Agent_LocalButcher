"""seed order statuses

Revision ID: 596085d8e353
Revises: 4c70978cbfe5
Create Date: 2026-07-24 16:18:05.954538

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '596085d8e353'
down_revision: Union[str, None] = '4c70978cbfe5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


import uuid
from alembic import op
from sqlalchemy import table, column, String, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID

order_statuses = table(
    "order_statuses",
    column("id", UUID),
    column("code", String),
    column("label", String),
    column("is_modifiable", Boolean),
    column("is_cancellable", Boolean),
    column("sort_order", Integer),
)

STATUSES = [
    {"code": "pending", "label": "Pending", "is_modifiable": True, "is_cancellable": True, "sort_order": 1},
    {"code": "confirmed", "label": "Confirmed", "is_modifiable": True, "is_cancellable": True, "sort_order": 2},
    {"code": "packed", "label": "Packed", "is_modifiable": False, "is_cancellable": False, "sort_order": 3},
    {"code": "out_for_delivery", "label": "Out for delivery", "is_modifiable": False, "is_cancellable": False, "sort_order": 4},
    {"code": "delivered", "label": "Delivered", "is_modifiable": False, "is_cancellable": False, "sort_order": 5},
    {"code": "cancelled", "label": "Cancelled", "is_modifiable": False, "is_cancellable": False, "sort_order": 6},
]


def upgrade() -> None:
    op.bulk_insert(order_statuses, [{**s, "id": uuid.uuid4()} for s in STATUSES])


def downgrade() -> None:
    op.execute("DELETE FROM order_statuses WHERE code IN ({})".format(
        ",".join(f"'{s['code']}'" for s in STATUSES)
    ))
