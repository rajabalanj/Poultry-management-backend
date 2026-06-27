"""add_foreign_key_to_operational_expenses

Revision ID: aecb611b4c46
Revises: c5cc51a81409
Create Date: 2026-06-25 22:17:49.946064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aecb611b4c46'
down_revision: Union[str, None] = 'c5cc51a81409'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_foreign_key(
        'fk_operational_expenses_account_id',
        'operational_expenses',
        'chart_of_accounts',
        ['account_id'],
        ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'fk_operational_expenses_account_id',
        'operational_expenses',
        type_='foreignkey'
    )
