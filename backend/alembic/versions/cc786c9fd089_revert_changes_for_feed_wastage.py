"""revert changes for feed wastage

Revision ID: cc786c9fd089
Revises: 6598c883dc3e
Create Date: 2025-07-21 19:05:53.760637

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc786c9fd089'
down_revision: Union[str, None] = '6598c883dc3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    # op.drop_index('ix_app_config_id', table_name='app_config')
    # op.drop_table('app_config')
    op.add_column('composition_usage_history', sa.Column('times', sa.Integer(), nullable=False))
    op.drop_column('composition_usage_history', 'wastage')
    op.drop_column('composition_usage_history', 'weight_of_composition')
    op.drop_column('feed_in_composition', 'wastage_in_percentage')
    op.drop_column('feed_in_composition', 'wastage_in_kg')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('feed_in_composition', sa.Column('wastage_in_kg', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.add_column('feed_in_composition', sa.Column('wastage_in_percentage', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.add_column('composition_usage_history', sa.Column('weight_of_composition', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False))
    op.add_column('composition_usage_history', sa.Column('wastage', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.drop_column('composition_usage_history', 'times')
    # op.create_table('app_config',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('name', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    # sa.Column('value', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    # sa.PrimaryKeyConstraint('id', name='app_config_pkey'),
    # sa.UniqueConstraint('name', name='app_config_name_key')
    # )
    # op.create_index('ix_app_config_id', 'app_config', ['id'], unique=False)
    # ### end Alembic commands ###
