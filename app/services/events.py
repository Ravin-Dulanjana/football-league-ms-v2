"""
Domain event system — Transactional Outbox Pattern.

Writing events
──────────────
Call `queue_event(db, event_type, payload)` BEFORE `db.commit()`.  It writes
an OutboxEvent row into the same transaction as your business write.  If the
commit fails, the event row is rolled back atomically — no phantom events.

Publishing events
─────────────────
`outbox_relay.py` runs via APScheduler (started in main.py's lifespan).  The
relay polls outbox_events WHERE sent=False, publishes each one to SQS, then
marks it sent=True only after the SQS SendMessage call returns OK.

If SQS is down the row stays unsent and the relay retries on the next tick
(~250–500 ms).  Delivery is at-least-once: the Lambda consumer must be
idempotent (a duplicate "registration.requested" email should be a no-op).

Message envelope (identical to the old fire-and-forget format):
    {
        "event_type": str,    e.g. "registration.requested"
        "payload":    dict,   event-specific fields including recipient_email
        "timestamp":  str,    ISO 8601 UTC (the outbox row's created_at)
        "version":    "1.0"
    }
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import boto3
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.outbox import OutboxEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API — called by service functions before db.commit()
# ---------------------------------------------------------------------------


def queue_event(db: Session, event_type: str, payload: dict[str, Any]) -> None:
    """
    Write a domain event to the outbox table inside the current transaction.

    Must be called BEFORE db.commit().  The event is published to SQS by the
    background relay; this function only writes the DB row.

    Silently skips (logs at DEBUG) when SQS_QUEUE_URL is not configured so
    local development and tests work without any SQS mocking.
    """
    if not settings.sqs_queue_url:
        logger.debug("SQS_QUEUE_URL not set — skipping outbox write: %s", event_type)
        return

    event = OutboxEvent(
        event_type=event_type,
        payload_json=json.dumps(payload),
    )
    db.add(event)
    logger.debug("Queued outbox event '%s'", event_type)


# ---------------------------------------------------------------------------
# Internal — called only by the relay
# ---------------------------------------------------------------------------


def _sqs_client() -> Any:
    return boto3.client("sqs", region_name=settings.aws_region)


def publish_pending(db: Session) -> None:
    """
    Relay: read unsent outbox rows, publish to SQS, mark sent.

    Called by APScheduler every ~300 ms.  Each call opens its own short-lived
    transaction scoped to this session; the caller (outbox_relay.py) manages
    the session lifecycle.

    Errors per-row are logged and skipped — they will be retried next tick.
    """
    rows = (
        db.execute(
            select(OutboxEvent)
            .where(OutboxEvent.sent.is_(False))
            .order_by(OutboxEvent.created_at)
            .limit(50)
            .with_for_update(skip_locked=True)
        )
        .scalars()
        .all()
    )

    if not rows:
        return

    client = _sqs_client()

    for row in rows:
        try:
            payload = json.loads(row.payload_json)
            message: dict[str, Any] = {
                "event_type": row.event_type,
                "payload": payload,
                "timestamp": row.created_at.isoformat()
                if row.created_at.tzinfo
                else row.created_at.replace(tzinfo=UTC).isoformat(),
                "version": "1.0",
            }
            client.send_message(
                QueueUrl=settings.sqs_queue_url,
                MessageBody=json.dumps(message),
            )
            row.sent = True
            row.sent_at = datetime.now(tz=UTC)
            logger.info("Published outbox event '%s' (id=%d)", row.event_type, row.id)
        except Exception:
            logger.exception(
                "Failed to publish outbox event '%s' (id=%d) — will retry",
                row.event_type,
                row.id,
            )

    db.commit()
