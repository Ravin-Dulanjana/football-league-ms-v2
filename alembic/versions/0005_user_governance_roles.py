"""Add user_governance_roles junction table for multi-role stacking.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_governance_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "club_id",
            sa.Integer(),
            sa.ForeignKey("clubs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("assigned_by_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(512), nullable=False, server_default=""),
    )
    op.create_index("ix_ugr_user_id", "user_governance_roles", ["user_id"])

    # Back-fill: every existing user's current role becomes their first
    # governance role entry (skip purely-base roles player/club_staff/user
    # that carry no governance meaning on their own — those are member_type).
    op.execute(
        """
        INSERT INTO user_governance_roles (user_id, role, club_id, reason)
        SELECT id, role, club_id, 'Migrated from users.role'
        FROM users
        WHERE role IN ('super_admin', 'league_admin', 'club_admin')
          AND is_deleted = false
        """
    )


def downgrade() -> None:
    op.drop_index("ix_ugr_user_id", table_name="user_governance_roles")
    op.drop_table("user_governance_roles")
