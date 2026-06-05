"""Add gender column to matches

Revision ID: 0001
Revises:
Create Date: 2026-06-05

Adds the 'gender' column to the 'matches' table.
Previously applied via a manual ALTER TABLE in main.py.
This migration is idempotent — it silently skips if the column
already exists (which it will for any existing database).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch mode for SQLite compatibility.
    # The column may already exist from the manual ALTER TABLE in main.py,
    # so we wrap in a try/except for idempotency.
    try:
        with op.batch_alter_table('matches', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('gender', sa.String(10), nullable=False, server_default='male')
            )
    except Exception:
        pass  # Column already exists


def downgrade() -> None:
    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.drop_column('gender')
