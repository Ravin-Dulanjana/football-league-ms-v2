"""Add min/max squad size limits to seasons.

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "seasons",
        sa.Column("min_squad_size", sa.Integer(), nullable=False, server_default="17"),
    )
    op.add_column(
        "seasons",
        sa.Column("max_squad_size", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade() -> None:
    op.drop_column("seasons", "max_squad_size")
    op.drop_column("seasons", "min_squad_size")
