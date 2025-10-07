"""make_egg_room_reports_pk_composite

Revision ID: 40e14d4a6f83
Revises: b76ead9195e8
Create Date: 2025-10-04 10:17:10.333849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40e14d4a6f83'
down_revision: Union[str, None] = 'b76ead9195e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
