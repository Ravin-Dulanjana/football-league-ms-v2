"""Late submission: is_late on profiles, approver_club_id on unlock_approvals

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-16
"""

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "club_season_profiles",
        sa.Column("is_late", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "unlock_approvals",
        sa.Column(
            "approver_club_id",
            sa.Integer(),
            sa.ForeignKey("clubs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("unlock_approvals", "approver_club_id")
    op.drop_column("club_season_profiles", "is_late")
