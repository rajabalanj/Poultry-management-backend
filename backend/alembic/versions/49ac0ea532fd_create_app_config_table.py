"""create app config table

Revision ID: 49ac0ea532fd
Revises: c54743fe68d3
Create Date: 2025-06-19 07:44:31.712051

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49ac0ea532fd'
down_revision: Union[str, None] = 'c54743fe68d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
