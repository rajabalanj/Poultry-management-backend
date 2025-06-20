"""alter shed_no data type

Revision ID: 3965852a53de
Revises: 5c2994a762bd
Create Date: 2025-06-03 17:18:11.219886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3965852a53de'
down_revision: Union[str, None] = '5c2994a762bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('batch', 'shed_no',
               existing_type=sa.INTEGER(),
               type_=sa.String(),
               existing_nullable=True)
    op.create_unique_constraint(None, 'batch', ['shed_no'])
    op.alter_column('daily_batch', 'shed_no',
               existing_type=sa.INTEGER(),
               type_=sa.String(),
               existing_nullable=True)
    op.create_unique_constraint(None, 'daily_batch', ['shed_no'])
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'daily_batch', type_='unique')
    op.alter_column('daily_batch', 'shed_no',
               existing_type=sa.String(),
               type_=sa.INTEGER(),
               existing_nullable=True)
    op.drop_constraint(None, 'batch', type_='unique')
    op.alter_column('batch', 'shed_no',
               existing_type=sa.String(),
               type_=sa.INTEGER(),
               existing_nullable=True)
    # ### end Alembic commands ###
