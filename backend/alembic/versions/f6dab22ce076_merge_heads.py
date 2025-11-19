"""merge heads

Revision ID: f6dab22ce076
Revises: 68981ed1dc8e, e9da5fb31ab6
Create Date: 2025-11-19 16:09:05.197623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6dab22ce076'
down_revision: Union[str, None] = ('68981ed1dc8e', 'e9da5fb31ab6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
