"""Initial schema — all tables for Phase 1.

Revision ID: 0001
Revises:
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum types (PostgreSQL native)
    # ------------------------------------------------------------------
    clubstatus = sa.Enum("active", "inactive", "suspended", name="clubstatus")
    seasonstatus = sa.Enum("draft", "open", "closed", "archived", name="seasonstatus")
    playerstatus = sa.Enum("pending_claim", "active", "inactive", name="playerstatus")
    registrationrequeststatus = sa.Enum(
        "pending_player_confirmation",
        "accepted",
        "rejected",
        "cancelled",
        name="registrationrequeststatus",
    )
    registrationtype = sa.Enum("new", "renewal", "transfer", name="registrationtype")
    playerseasonregistrationstatus = sa.Enum(
        "active", "released", "cancelled", name="playerseasonregistrationstatus"
    )
    releasestatus = sa.Enum(
        "pending_player_confirmation",
        "confirmed",
        "rejected",
        "cancelled",
        name="releasestatus",
    )

    # ------------------------------------------------------------------
    # clubs
    # ------------------------------------------------------------------
    op.create_table(
        "clubs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("short_name", sa.String(32), nullable=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("logo_url", sa.String(512), nullable=True),
        sa.Column(
            "status",
            clubstatus,
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # seasons
    # ------------------------------------------------------------------
    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("registration_open_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registration_close_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_locked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "status",
            seasonstatus,
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("year", name="unique_year"),
    )
    op.create_index("ix_seasons_status", "seasons", ["status"])

    # ------------------------------------------------------------------
    # players
    # ------------------------------------------------------------------
    op.create_table(
        "players",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("league_player_code", sa.String(32), nullable=False, unique=True),
        sa.Column("full_name", sa.String(128), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("nic_number", sa.String(24), nullable=False, unique=True),
        sa.Column("photo_url", sa.String(512), nullable=True),
        sa.Column(
            "status",
            playerstatus,
            nullable=False,
            server_default="pending_claim",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_players_league_player_code", "players", ["league_player_code"])
    op.create_index("ix_players_nic_number", "players", ["nic_number"])

    # ------------------------------------------------------------------
    # registration_requests
    # ------------------------------------------------------------------
    op.create_table(
        "registration_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "season_id",
            sa.Integer,
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "club_id",
            sa.Integer,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "player_id",
            sa.Integer,
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requested_by_user_id", sa.Integer, nullable=False),
        sa.Column(
            "status",
            registrationrequeststatus,
            nullable=False,
            server_default="pending_player_confirmation",
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_reg_requests_season_club_status",
        "registration_requests",
        ["season_id", "club_id", "status"],
    )

    # ------------------------------------------------------------------
    # player_season_registrations
    # ------------------------------------------------------------------
    op.create_table(
        "player_season_registrations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "season_id",
            sa.Integer,
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "club_id",
            sa.Integer,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "player_id",
            sa.Integer,
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "registration_type",
            registrationtype,
            nullable=False,
            server_default="new",
        ),
        sa.Column(
            "status",
            playerseasonregistrationstatus,
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "player_id", "season_id", name="uq_player_season_registration"
        ),
    )
    op.create_index(
        "ix_psr_club_season_status",
        "player_season_registrations",
        ["club_id", "season_id", "status"],
    )

    # ------------------------------------------------------------------
    # player_releases
    # ------------------------------------------------------------------
    op.create_table(
        "player_releases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "registration_id",
            sa.Integer,
            sa.ForeignKey("player_season_registrations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "player_id",
            sa.Integer,
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_club_id",
            sa.Integer,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            releasestatus,
            nullable=False,
            server_default="pending_player_confirmation",
        ),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_releases_from_club_status", "player_releases", ["from_club_id", "status"]
    )
    op.create_index(
        "ix_releases_player_status", "player_releases", ["player_id", "status"]
    )

    # ------------------------------------------------------------------
    # release_documents
    # ------------------------------------------------------------------
    op.create_table(
        "release_documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "release_id",
            sa.Integer,
            sa.ForeignKey("player_releases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_url", sa.String(512), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.drop_table("release_documents")
    op.drop_table("player_releases")
    op.drop_table("player_season_registrations")
    op.drop_table("registration_requests")
    op.drop_table("players")
    op.drop_table("seasons")
    op.drop_table("clubs")

    # Drop PostgreSQL enum types
    sa.Enum(name="releasestatus").drop(op.get_bind())
    sa.Enum(name="playerseasonregistrationstatus").drop(op.get_bind())
    sa.Enum(name="registrationtype").drop(op.get_bind())
    sa.Enum(name="registrationrequeststatus").drop(op.get_bind())
    sa.Enum(name="playerstatus").drop(op.get_bind())
    sa.Enum(name="seasonstatus").drop(op.get_bind())
    sa.Enum(name="clubstatus").drop(op.get_bind())
