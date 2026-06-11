"""Add club fields (established_year, phone, officials) and league_info table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Club new fields
    op.add_column("clubs", sa.Column("phone_number", sa.String(32), nullable=True))
    op.add_column("clubs", sa.Column("established_year", sa.Integer(), nullable=True))
    op.add_column("clubs", sa.Column("president_name", sa.String(128), nullable=True))
    op.add_column("clubs", sa.Column("secretary_name", sa.String(128), nullable=True))
    op.add_column("clubs", sa.Column("treasurer_name", sa.String(128), nullable=True))

    # League info singleton — only one row ever exists (id=1)
    op.create_table(
        "league_info",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_name", sa.String(256), nullable=False, server_default=""),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("president_name", sa.String(128), nullable=True),
        sa.Column("secretary_name", sa.String(128), nullable=True),
        sa.Column("treasurer_name", sa.String(128), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(32), nullable=True),
        sa.Column("logo_key", sa.String(512), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    # Seed the singleton row
    op.execute("INSERT INTO league_info (id, league_name) VALUES (1, '')")


def downgrade() -> None:
    op.drop_table("league_info")
    op.drop_column("clubs", "treasurer_name")
    op.drop_column("clubs", "secretary_name")
    op.drop_column("clubs", "president_name")
    op.drop_column("clubs", "established_year")
    op.drop_column("clubs", "phone_number")
