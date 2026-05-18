"""add_is_sellable_to_inventory_items

Revision ID: 5547e4fc4de7
Revises: 202b49fbccb0
Create Date: 2026-05-14 23:14:04.560030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5547e4fc4de7'
down_revision: Union[str, None] = '202b49fbccb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('inventory_items', sa.Column('is_sellable', sa.Boolean(), server_default='false', nullable=False))
    # Set is_sellable=True for items in 'Supplies' category and egg items
    op.execute("""
        UPDATE inventory_items 
        SET is_sellable = TRUE 
        WHERE category = 'Supplies' OR name IN ('Table Egg', 'Jumbo Egg', 'Grade C Egg')
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('inventory_items', 'is_sellable')
