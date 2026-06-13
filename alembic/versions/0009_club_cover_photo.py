"""Add cover_key to clubs

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-13
"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clubs", sa.Column("cover_key", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("clubs", "cover_key")
