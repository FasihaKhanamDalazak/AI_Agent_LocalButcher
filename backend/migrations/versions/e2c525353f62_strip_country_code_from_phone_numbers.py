"""strip country code from phone numbers

Phone numbers were stored E.164 ("+91XXXXXXXXXX"), a convention picked
before the phone-call agent existed. In practice it only ever created a
way for a caller's spoken number (transcribed, then normalized in
auth_service._normalize_phone) to mismatch what was actually stored,
observed directly against a real deployed call — verification that
worked once then failed on a second attempt with no code change in
between, traced to country-code handling being the point of divergence.
Since this project serves only the Indian market (see backend
CLAUDE.md), the country code added a real bug surface for zero benefit.
Storage moves to a plain 10-digit number, no "+91", matching
UserCreate.phone's new pattern (app/schemas/user.py) and
auth_service._normalize_phone's simplified output.

Revision ID: e2c525353f62
Revises: 884d16480f97
Create Date: 2026-07-26 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2c525353f62'
down_revision: Union[str, None] = '884d16480f97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE users SET phone = substring(phone from 4) WHERE phone LIKE '+91%'"))


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE users SET phone = '+91' || phone WHERE phone ~ '^[6-9][0-9]{9}$'")
    )
