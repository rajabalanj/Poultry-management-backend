
"""add egg_prices table

Revision ID: 20240401_add_egg_prices_table
Revises: 
Create Date: 2024-04-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20240401_add_egg_prices_table'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create egg_prices table
    op.create_table(
        'egg_prices',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('price_date', sa.Date(), nullable=False),
        sa.Column('single_egg_rate', sa.String(), nullable=True),
        sa.Column('dozen_eggs_rate', sa.String(), nullable=True),
        sa.Column('hundred_eggs_rate', sa.String(), nullable=True),
        sa.Column('average_market_price', sa.String(), nullable=True),
        sa.Column('best_market_price', sa.String(), nullable=True),
        sa.Column('lowest_market_price', sa.String(), nullable=True),
        sa.Column('best_price_market', sa.String(), nullable=True),
        sa.Column('lowest_price_market', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index on price_date for faster lookups
    op.create_index(op.f('ix_egg_prices_price_date'), 'egg_prices', ['price_date'], unique=True)


def downgrade() -> None:
    # Drop egg_prices table
    op.drop_index(op.f('ix_egg_prices_price_date'), table_name='egg_prices')
    op.drop_table('egg_prices')
