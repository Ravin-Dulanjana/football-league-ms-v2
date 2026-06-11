"""Season end date + active status; club_id on players; club_membership_requests table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-11

Season restructure:
  - seasons.season_end_date  — rough end date for the season
  - seasonstatus enum gets 'active' between 'open' and 'closed'

Club membership restructure:
  - players.club_id          — which club the player currently belongs to (null = free)
  - club_membership_requests — invite flow (not season-scoped)
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add 'active' to the seasonstatus enum.
    #    PostgreSQL: ALTER TYPE is DDL; SQLite stores enums as VARCHAR so
    #    nothing is needed there.
    # ------------------------------------------------------------------
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sql = "ALTER TYPE seasonstatus ADD VALUE IF NOT EXISTS 'active' AFTER 'open'"
        op.execute(sql)

    # ------------------------------------------------------------------
    # 2. seasons: add season_end_date
    # ------------------------------------------------------------------
    op.add_column(
        "seasons",
        sa.Column("season_end_date", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # 3. players: add club_id (nullable FK → clubs.id)
    # ------------------------------------------------------------------
    op.add_column(
        "players",
        sa.Column("club_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_players_club_id",
        "players",
        "clubs",
        ["club_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_players_club_id", "players", ["club_id"])

    # ------------------------------------------------------------------
    # 4. club_membership_requests table
    #    Replaces season-scoped registration requests for the "join a club"
    #    flow.  Invitations are not tied to a season.
    # ------------------------------------------------------------------
    op.create_table(
        "club_membership_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "club_id",
            sa.Integer(),
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_cmr_player_status", "club_membership_requests", ["player_id", "status"]
    )
    op.create_index(
        "ix_cmr_club_status", "club_membership_requests", ["club_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("club_membership_requests")
    op.drop_index("ix_players_club_id", table_name="players")
    op.drop_constraint("fk_players_club_id", "players", type_="foreignkey")
    op.drop_column("players", "club_id")
    op.drop_column("seasons", "season_end_date")
    # Note: removing an enum value in PostgreSQL is not supported without
    # recreating the type.  For SQLite, no-op.
