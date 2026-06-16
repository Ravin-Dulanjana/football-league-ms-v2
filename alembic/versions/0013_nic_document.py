"""NIC document: nic_document_key column on players

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-16
"""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("nic_document_key", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("players", "nic_document_key")
