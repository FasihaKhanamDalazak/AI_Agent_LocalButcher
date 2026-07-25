"""rename madhapur outlet for naming consistency

The Madhapur outlet predates the seed migrations (3aa804451344) — it was
one of the original manually-inserted rows via Supabase's Table Editor
(see backend/README.md's "Current data" note), never renamed when the
other 8 outlets were seeded under the "Local Butcher - <Area>" convention.
This brings it in line: "Outlet_1" -> "Local Butcher - Madhapur".

Revision ID: 884d16480f97
Revises: 3aa804451344
Create Date: 2026-07-25 20:17:10.001260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '884d16480f97'
down_revision: Union[str, None] = '3aa804451344'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE outlets SET name = 'Local Butcher - Madhapur' WHERE name = 'Outlet_1' AND area = 'Madhapur'")
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE outlets SET name = 'Outlet_1' WHERE name = 'Local Butcher - Madhapur' AND area = 'Madhapur'"
        )
    )
