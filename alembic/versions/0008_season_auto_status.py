"""Replace manual status/is_locked columns with is_archived flag.

Status is now computed from the three date fields at read time:
  before registration_open_at  → draft
  open_at ≤ now ≤ close_at     → open
  close_at < now ≤ end_date    → active   (or indefinitely active if no end date)
  after season_end_date        → closed
  is_archived = True           → archived  (only manual state)

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("seasons") as batch_op:
        batch_op.drop_column("is_locked")
        batch_op.drop_column("status")
        batch_op.add_column(
            sa.Column(
                "is_archived",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # PostgreSQL: drop the now-unused seasonstatus enum type.
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS seasonstatus")

    # Drop the index on the removed status column (SQLite ignores missing indexes).
    if bind.dialect.name == "postgresql":
        op.drop_index("ix_seasons_status", table_name="seasons", if_exists=True)


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE TYPE seasonstatus AS ENUM "
            "('draft', 'open', 'active', 'closed', 'archived')"
        )

    with op.batch_alter_table("seasons") as batch_op:
        batch_op.drop_column("is_archived")
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(32)
                if bind.dialect.name != "postgresql"
                else sa.Enum(
                    "draft",
                    "open",
                    "active",
                    "closed",
                    "archived",
                    name="seasonstatus",
                ),
                nullable=False,
                server_default="draft",
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_locked", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
