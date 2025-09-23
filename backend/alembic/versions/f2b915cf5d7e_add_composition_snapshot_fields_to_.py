"""add composition snapshot fields to usage history

Revision ID: f2b915cf5d7e
Revises: 25d6a43aca93
Create Date: 2025-09-23 00:01:35.462913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2b915cf5d7e'
down_revision: Union[str, None] = '25d6a43aca93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns as nullable first
    op.add_column('composition_usage_history', sa.Column('composition_name', sa.String(), nullable=True))
    op.add_column('composition_usage_history', sa.Column('composition_items', sa.JSON(), nullable=True))

    # Data migration to populate existing rows
    connection = op.get_bind()
    
    # Use raw SQL to update the composition_name for existing rows
    # This is a common pattern for data migrations in Alembic
    connection.execute(sa.text("""
        UPDATE composition_usage_history
        SET composition_name = composition.name
        FROM composition
        WHERE composition_usage_history.composition_id = composition.id
        AND composition_usage_history.composition_name IS NULL
    """))

    # For composition_items, it's more complex to construct the JSON in pure SQL
    # across different DBs. We'll fetch and update.
    # A more complex but pure SQL approach might be possible depending on the DB.
    
    histories = connection.execute(sa.text("SELECT id, composition_id FROM composition_usage_history WHERE composition_items IS NULL")).fetchall()
    
    for history_id, composition_id in histories:
        items = connection.execute(sa.text(f"""
            SELECT iic.inventory_item_id, i.name, iic.weight
            FROM inventory_item_in_composition AS iic
            JOIN inventory_items AS i ON iic.inventory_item_id = i.id
            WHERE iic.composition_id = {composition_id}
        """)).fetchall()
        
        composition_items = [
            {
                "inventory_item_id": item_id,
                "inventory_item_name": name,
                "weight": float(weight),
                "unit": "kg"
            }
for item_id, name, weight in items
        ]
        
        # SQLAlchemy's JSON type handles the serialization
        connection.execute(
            sa.text("UPDATE composition_usage_history SET composition_items = :items WHERE id = :id"),
            {"items": sa.JSON().process_bind_param(composition_items, connection.dialect), "id": history_id}
        )

    # Now that the data is backfilled, make the columns non-nullable
    op.alter_column('composition_usage_history', 'composition_name', nullable=False)
    op.alter_column('composition_usage_history', 'composition_items', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('composition_usage_history', 'composition_items')
    op.drop_column('composition_usage_history', 'composition_name')