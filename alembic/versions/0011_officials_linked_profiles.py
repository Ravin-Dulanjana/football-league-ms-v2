"""Link president/secretary/treasurer to player profiles in clubs and league_info

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-16
"""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clubs",
        sa.Column(
            "president_player_id",
            sa.Integer,
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "clubs",
        sa.Column(
            "secretary_player_id",
            sa.Integer,
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "clubs",
        sa.Column(
            "treasurer_player_id",
            sa.Integer,
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.add_column(
        "league_info",
        sa.Column(
            "president_player_id",
            sa.Integer,
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "league_info",
        sa.Column(
            "secretary_player_id",
            sa.Integer,
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "league_info",
        sa.Column(
            "treasurer_player_id",
            sa.Integer,
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    for col in (
        "president_player_id",
        "secretary_player_id",
        "treasurer_player_id",
    ):
        op.drop_column("clubs", col)
        op.drop_column("league_info", col)
