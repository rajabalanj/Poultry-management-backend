"""removed chick_batch column

Revision ID: f5e7fb7f0b0a
Revises: cc786c9fd089
Create Date: 2025-07-21 21:06:42.646324

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5e7fb7f0b0a'
down_revision: Union[str, None] = 'cc786c9fd089'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    # op.drop_index('ix_app_config_id', table_name='app_config')
    # op.drop_table('app_config')
    op.drop_column('batch', 'is_chick_batch')
    op.drop_column('daily_batch', 'is_chick_batch')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('daily_batch', sa.Column('is_chick_batch', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.add_column('batch', sa.Column('is_chick_batch', sa.BOOLEAN(), autoincrement=False, nullable=True))
    # op.create_table('app_config',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('name', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    # sa.Column('value', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    # sa.PrimaryKeyConstraint('id', name='app_config_pkey'),
    # sa.UniqueConstraint('name', name='app_config_name_key')
    # )
    # op.create_index('ix_app_config_id', 'app_config', ['id'], unique=False)
    # ### end Alembic commands ###
