"""Add last_logout_at to users table for token revocation

Revision ID: 002_add_user_last_logout_at
Revises: 001_add_outbox_events
Create Date: 2026-08-23

After Cognito GlobalSignOut the refresh token is revoked immediately, but the
ID/access tokens remain valid until their `exp` claim (up to 1 hour).  We
close this gap by stamping `last_logout_at` on the User row at logout.
`get_current_user` rejects any token whose `iat` is before that timestamp.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_add_user_last_logout_at"
down_revision: str = "001_add_outbox_events"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_logout_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_logout_at")
