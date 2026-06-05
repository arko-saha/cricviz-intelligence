"""Add commentary_text column to deliveries

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-05

Adds the 'commentary_text' TEXT column to the 'deliveries' table.
Previously applied via a manual ALTER TABLE in main.py.
This migration is idempotent — it silently skips if the column
already exists (which it will for any existing database).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch mode for SQLite compatibility.
    # The column may already exist from the manual ALTER TABLE in main.py,
    # so we wrap in a try/except for idempotency.
    try:
        with op.batch_alter_table('deliveries', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('commentary_text', sa.Text(), nullable=True)
            )
    except Exception:
        pass  # Column already exists


def downgrade() -> None:
    with op.batch_alter_table('deliveries', schema=None) as batch_op:
        batch_op.drop_column('commentary_text')
