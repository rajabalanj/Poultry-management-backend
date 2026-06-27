"""merge heads

Revision ID: 4156f1cb117f
Revises: eab99fa03509, repl_exp_type_with_acc_id
Create Date: 2026-06-24 19:30:10.555926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4156f1cb117f'
down_revision: Union[str, None] = ('eab99fa03509', 'repl_exp_type_with_acc_id')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
