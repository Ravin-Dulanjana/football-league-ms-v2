"""Add member_type to users; support club_staff role.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-11

Changes:
  - users: add member_type column (nullable varchar 32)
    "player"     — user has a player profile (footballer)
    "club_staff" — user is club staff (coach, physio, etc.) without a player profile
    NULL         — super_admin or league-only admin with no club membership
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("member_type", sa.String(32), nullable=True),
    )
    # Back-fill existing rows: player roles get member_type="player"
    op.execute("UPDATE users SET member_type = 'player' WHERE role = 'player'")


def downgrade() -> None:
    op.drop_column("users", "member_type")
