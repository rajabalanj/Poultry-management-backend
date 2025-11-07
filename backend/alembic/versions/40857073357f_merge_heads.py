"""merge heads

Revision ID: 40857073357f
Revises: 598577237992, g279a49782e4
Create Date: 2025-11-06 14:59:36.309029

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40857073357f'
down_revision: Union[str, None] = ('598577237992', 'g279a49782e4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
