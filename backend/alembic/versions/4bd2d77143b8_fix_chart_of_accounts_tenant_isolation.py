"""fix_chart_of_accounts_tenant_isolation

Revision ID: 4bd2d77143b8
Revises: 0216d3958685
Create Date: 2026-02-11 11:12:37.742113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4bd2d77143b8'
down_revision: Union[str, None] = '0216d3958685'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the existing unique constraint on account_code
    op.drop_constraint('chart_of_accounts_account_code_key', 'chart_of_accounts', type_='unique')
    
    # Add composite unique constraint for tenant_id and account_code
    op.create_unique_constraint('_tenant_account_code_uc', 'chart_of_accounts', ['tenant_id', 'account_code'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the composite unique constraint
    op.drop_constraint('_tenant_account_code_uc', 'chart_of_accounts', type_='unique')
    
    # Restore the original unique constraint on account_code
    op.create_unique_constraint('chart_of_accounts_account_code_key', 'chart_of_accounts', ['account_code'])
