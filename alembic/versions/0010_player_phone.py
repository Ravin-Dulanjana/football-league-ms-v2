"""Add phone_number to players

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-16
"""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("phone_number", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "phone_number")
