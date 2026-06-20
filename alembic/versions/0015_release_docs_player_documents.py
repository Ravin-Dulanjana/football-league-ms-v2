"""make registration_id nullable in player_releases; add player_documents table

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-21

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Make registration_id nullable — remove the unique + not-null constraints.
    #    New-style direct releases don't require an active registration.
    op.drop_index("ix_releases_from_club_status", table_name="player_releases")
    op.drop_index("ix_releases_player_status", table_name="player_releases")

    op.alter_column(
        "player_releases",
        "registration_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    # The implicit unique index created by unique=True in SQLAlchemy is named
    # after the column by Postgres convention.
    op.drop_constraint(
        "player_releases_registration_id_key", "player_releases", type_="unique"
    )
    # Switch FK to SET NULL — deleting a registration keeps the release record.
    op.drop_constraint(
        "player_releases_registration_id_fkey", "player_releases", type_="foreignkey"
    )
    op.create_foreign_key(
        "player_releases_registration_id_fkey",
        "player_releases",
        "player_season_registrations",
        ["registration_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_releases_from_club_status", "player_releases", ["from_club_id", "status"]
    )
    op.create_index(
        "ix_releases_player_status", "player_releases", ["player_id", "status"]
    )

    # 2. Create player_documents table for self-uploaded external release letters
    op.create_table(
        "player_documents",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_player_documents_player_id", "player_documents", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_player_documents_player_id", table_name="player_documents")
    op.drop_table("player_documents")

    op.drop_index("ix_releases_from_club_status", table_name="player_releases")
    op.drop_index("ix_releases_player_status", table_name="player_releases")

    op.drop_constraint(
        "player_releases_registration_id_fkey", "player_releases", type_="foreignkey"
    )
    op.create_foreign_key(
        "player_releases_registration_id_fkey",
        "player_releases",
        "player_season_registrations",
        ["registration_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "player_releases_registration_id_key", "player_releases", ["registration_id"]
    )
    op.alter_column(
        "player_releases",
        "registration_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_index(
        "ix_releases_from_club_status", "player_releases", ["from_club_id", "status"]
    )
    op.create_index(
        "ix_releases_player_status", "player_releases", ["player_id", "status"]
    )
