"""add new column rename some columns

Revision ID: 36f7488cd139
Revises: f1bd2dd6af6d
Create Date: 2025-06-04 09:07:08.919325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36f7488cd139'
down_revision: Union[str, None] = 'f1bd2dd6af6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('batch', sa.Column('table_eggs', sa.Integer(), nullable=True))
    op.add_column('batch', sa.Column('hd', sa.Numeric(precision=11, scale=9), nullable=True))
    op.add_column('batch', sa.Column('is_chick_batch', sa.Boolean(), nullable=True))
    op.drop_column('batch', 'HD')
    op.drop_column('batch', 'table')
    op.add_column('daily_batch', sa.Column('hd', sa.Numeric(precision=11, scale=9), nullable=True))
    op.add_column('daily_batch', sa.Column('table_eggs', sa.Integer(), nullable=True))
    op.add_column('daily_batch', sa.Column('is_chick_batch', sa.Boolean(), nullable=True))
    op.drop_column('daily_batch', 'HD')
    op.drop_column('daily_batch', 'table')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('daily_batch', sa.Column('table', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('daily_batch', sa.Column('HD', sa.NUMERIC(precision=11, scale=9), autoincrement=False, nullable=True))
    op.drop_column('daily_batch', 'is_chick_batch')
    op.drop_column('daily_batch', 'table_eggs')
    op.drop_column('daily_batch', 'hd')
    op.add_column('batch', sa.Column('table', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('batch', sa.Column('HD', sa.NUMERIC(precision=11, scale=9), autoincrement=False, nullable=True))
    op.drop_column('batch', 'is_chick_batch')
    op.drop_column('batch', 'hd')
    op.drop_column('batch', 'table_eggs')
    # ### end Alembic commands ###
