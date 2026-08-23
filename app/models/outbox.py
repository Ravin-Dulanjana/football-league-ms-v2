"""
Transactional Outbox — outbox_events table.

Each row represents a domain event that must be published to SQS.
The relay in app/services/outbox_relay.py reads unsent rows and publishes
them, marking each row sent=True only after the SQS send is confirmed.

Why this beats fire-and-forget publish_event:
  - The INSERT happens inside the same db.commit() as the business write.
    If the commit fails, no phantom event is published.
  - If SQS is down when the relay runs, the row stays unsent and will be
    retried on the next relay tick (every 250–500 ms).
  - At-least-once delivery: the Lambda consumer must be idempotent.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        # Relay query: WHERE sent = false ORDER BY created_at — needs this index.
        Index("ix_outbox_events_sent_created", "sent", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128))
    # JSON-encoded payload dict — Text so it can hold arbitrarily large payloads.
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    sent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
