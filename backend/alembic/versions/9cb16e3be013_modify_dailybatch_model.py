"""Modify DailyBatch model

Revision ID: 9cb16e3be013
Revises: 
Create Date: 2025-04-25 12:17:48.155820

"""
from typing import Sequence, Union
import logging

from alembic import op
import sqlalchemy as sa


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# revision identifiers, used by Alembic.
revision: str = '9cb16e3be013'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    logger.info("Starting upgrade for revision %s", revision)
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('daily_batch', 'batch_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('daily_batch', 'batch_date',
               existing_type=sa.DATE(),
               nullable=False)
    op.drop_index('ix_daily_batch_id', table_name='daily_batch')
    op.drop_column('daily_batch', 'id')
    # ### end Alembic commands ###
    logger.info("Upgrade completed for revision %s", revision)


def downgrade() -> None:
    """Downgrade schema."""
    logger.info("Starting downgrade for revision %s", revision)
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('daily_batch', sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False))
    op.create_index('ix_daily_batch_id', 'daily_batch', ['id'], unique=False)
    op.alter_column('daily_batch', 'batch_date',
               existing_type=sa.DATE(),
               nullable=True)
    op.alter_column('daily_batch', 'batch_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    # ### end Alembic commands ###
    logger.info("Downgrade completed for revision %s", revision)
