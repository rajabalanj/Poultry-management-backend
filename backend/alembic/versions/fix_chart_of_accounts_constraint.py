"""fix_chart_of_accounts_constraint

Revision ID: fix_chart_of_accounts_constraint
Revises: 4bd2d77143b8
Create Date: 2023-12-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fix_chart_of_accounts_constraint'
down_revision: Union[str, None] = '4bd2d77143b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if the constraint exists before dropping it
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    constraints = inspector.get_unique_constraints('chart_of_accounts')
    constraint_exists = any(c['name'] == 'chart_of_accounts_account_code_key' for c in constraints)

    if constraint_exists:
        # Drop the existing unique constraint on account_code
        op.drop_constraint('chart_of_accounts_account_code_key', 'chart_of_accounts', type_='unique')

    # Check if the composite constraint already exists
    composite_constraint_exists = any(c['name'] == '_tenant_account_code_uc' for c in constraints)

    if not composite_constraint_exists:
        # Add composite unique constraint for tenant_id and account_code
        op.create_unique_constraint('_tenant_account_code_uc', 'chart_of_accounts', ['tenant_id', 'account_code'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the composite unique constraint
    op.drop_constraint('_tenant_account_code_uc', 'chart_of_accounts', type_='unique')

    # Restore the original unique constraint on account_code
    op.create_unique_constraint('chart_of_accounts_account_code_key', 'chart_of_accounts', ['account_code'])
