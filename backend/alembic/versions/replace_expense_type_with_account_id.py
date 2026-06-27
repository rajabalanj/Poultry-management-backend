"""replace expense_type with account_id in operational_expenses

Revision ID: repl_exp_type_with_acc_id
Revises: 7254b9e6d9da
Create Date: 2025-06-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'repl_exp_type_with_acc_id'
down_revision: Union[str, None] = '7254b9e6d9da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # 1. Add account_id as nullable
    op.add_column('operational_expenses', sa.Column('account_id', sa.Integer(), nullable=True))

    # 2. Populate account_id from the default operational expense account in financial_settings
    bind.execute(sa.text("""
        UPDATE operational_expenses oe
        SET account_id = (
            SELECT default_operational_expense_account_id
            FROM financial_settings
            WHERE tenant_id = oe.tenant_id
        )
    """))

    # 3. Swap constraints and drop expense_type
    op.drop_constraint('_tenant_date_expense_uc', 'operational_expenses', type_='unique')
    op.alter_column('operational_expenses', 'account_id', nullable=False)
    op.create_unique_constraint('_tenant_date_account_uc', 'operational_expenses', ['tenant_id', 'expense_date', 'account_id'])
    op.drop_column('operational_expenses', 'expense_type')


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    # 1. Restore expense_type from account name
    op.add_column('operational_expenses', sa.Column('expense_type', sa.String(), nullable=True))
    bind.execute(sa.text("""
        UPDATE operational_expenses oe
        SET expense_type = (
            SELECT account_name FROM chart_of_accounts WHERE id = oe.account_id
        )
    """))
    op.alter_column('operational_expenses', 'expense_type', nullable=False)

    # 2. Swap constraints and drop account_id
    op.drop_constraint('_tenant_date_account_uc', 'operational_expenses', type_='unique')
    op.create_unique_constraint('_tenant_date_expense_uc', 'operational_expenses', ['tenant_id', 'expense_date', 'expense_type'])
    op.drop_column('operational_expenses', 'account_id')
