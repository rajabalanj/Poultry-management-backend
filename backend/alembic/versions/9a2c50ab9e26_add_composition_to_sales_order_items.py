"""add_composition_to_sales_order_items

Revision ID: 9a2c50ab9e26
Revises: 436610aec827
Create Date: 2026-06-26 22:25:00.002336

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a2c50ab9e26'
down_revision: Union[str, None] = '436610aec827'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make inventory_item_id nullable
    op.alter_column('sales_order_items', 'inventory_item_id', nullable=True)
    
    # Add composition_id column
    op.add_column('sales_order_items', sa.Column('composition_id', sa.Integer(), nullable=True))
    
    # Create foreign key constraint for composition_id
    op.create_foreign_key(
        'fk_sales_order_items_composition',
        'sales_order_items',
        'composition',
        ['composition_id'],
        ['id']
    )
    
    # Create check constraint to ensure exactly one is set
    op.create_check_constraint(
        'check_item_or_composition',
        'sales_order_items',
        '(inventory_item_id IS NOT NULL AND composition_id IS NULL) OR (inventory_item_id IS NULL AND composition_id IS NOT NULL)'
    )


def downgrade() -> None:
    # Drop check constraint
    op.drop_constraint('check_item_or_composition', 'sales_order_items', type_='check')
    
    # Drop foreign key constraint
    op.drop_constraint('fk_sales_order_items_composition', 'sales_order_items', type_='foreignkey')
    
    # Drop composition_id column
    op.drop_column('sales_order_items', 'composition_id')
    
    # Make inventory_item_id non-nullable again
    op.alter_column('sales_order_items', 'inventory_item_id', nullable=False)

