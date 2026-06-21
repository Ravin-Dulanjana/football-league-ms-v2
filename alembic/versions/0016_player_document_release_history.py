"""Add release history fields to player_documents.

Adds year, league_name, club_name, is_visible, source, and release_id
so player_documents can store a full personal release history (both
in-league releases auto-created on release, and manually uploaded
external release letters).

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-22
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("player_documents", sa.Column("year", sa.Integer(), nullable=True))
    op.add_column(
        "player_documents",
        sa.Column("league_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "player_documents",
        sa.Column("club_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "player_documents",
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "player_documents",
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column(
        "player_documents",
        sa.Column(
            "release_id",
            sa.Integer(),
            sa.ForeignKey("player_releases.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("player_documents", "release_id")
    op.drop_column("player_documents", "source")
    op.drop_column("player_documents", "is_visible")
    op.drop_column("player_documents", "club_name")
    op.drop_column("player_documents", "league_name")
    op.drop_column("player_documents", "year")
