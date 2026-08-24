"""Add outbox_events table for Transactional Outbox Pattern

Revision ID: 001_add_outbox_events
Revises:
Create Date: 2026-08-22

This table stores domain events that must be published to SQS.  The relay
in app/services/outbox_relay.py reads unsent rows and publishes them every
~300 ms, marking each row sent=True only after the SQS send is confirmed.

The index on (sent, created_at) covers the relay's WHERE sent=false ORDER BY
created_at query without a full table scan.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_add_outbox_events"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Relay query: WHERE sent = false ORDER BY created_at
    op.create_index(
        "ix_outbox_events_sent_created",
        "outbox_events",
        ["sent", "created_at"],
    )
    op.create_index(
        "ix_outbox_events_created_at",
        "outbox_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_created_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_sent_created", table_name="outbox_events")
    op.drop_table("outbox_events")
