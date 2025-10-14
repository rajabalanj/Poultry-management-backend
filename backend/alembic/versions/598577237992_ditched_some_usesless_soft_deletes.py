"""ditched some usesless soft deletes

Revision ID: 598577237992
Revises: d0644a1a6486
Create Date: 2025-10-15 01:33:15.074262

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '598577237992'
down_revision: Union[str, None] = 'd0644a1a6486'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns_in_table(conn, table_name: str) -> set:
    inspector = sa.inspect(conn)
    try:
        cols = {c['name'] for c in inspector.get_columns(table_name)}
    except Exception:
        cols = set()
    return cols


def upgrade() -> None:
    """Upgrade schema by removing only soft-delete columns where present."""
    conn = op.get_bind()
    tables = [
        'app_config',
        'batch',
        'egg_room_reports',
        'daily_batch',
        'bovanswhitelayerperformance',
        'business_partners',
        'composition',
        'inventory_items',
    ]

    for t in tables:
        cols = _columns_in_table(conn, t)
        if 'deleted_at' in cols:
            op.drop_column(t, 'deleted_at')
        if 'deleted_by' in cols:
            op.drop_column(t, 'deleted_by')


def downgrade() -> None:
    """Downgrade schema by re-adding soft-delete columns if missing."""
    conn = op.get_bind()
    tables = [
        'app_config',
        'batch',
        'egg_room_reports',
        'daily_batch',
        'bovanswhitelayerperformance',
        'business_partners',
        'composition',
        'inventory_items',
    ]

    for t in tables:
        cols = _columns_in_table(conn, t)
        if 'deleted_at' not in cols:
            op.add_column(t, sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        if 'deleted_by' not in cols:
            op.add_column(t, sa.Column('deleted_by', sa.String(), nullable=True))
