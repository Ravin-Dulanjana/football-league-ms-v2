"""
Domain event publisher.

Publishes structured JSON messages to the SQS notification queue after
successful database commits. The Lambda function reads from this queue
and sends emails via SES.

Fire-and-forget: SQS errors are logged but never re-raised. The business
transaction has already committed — a SQS outage must not cause the user
to see a failure when their registration or release succeeded.

⚠️  Known limitation: publishing after db.commit() means that if this call
    fails (SQS down, network partition), the notification is silently lost.
    The production fix is the Transactional Outbox Pattern: write the event
    to a DB table inside the same transaction, then a relay publishes to SQS.
    That pattern is out of scope for this phase.

Message envelope:
    {
        "event_type": str,    e.g. "registration.requested"
        "payload":    dict,   event-specific fields including recipient_email
        "timestamp":  str,    ISO 8601 UTC
        "version":    "1.0"
    }
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import boto3

from app.config import settings

logger = logging.getLogger(__name__)


def _sqs_client() -> Any:
    return boto3.client("sqs", region_name=settings.aws_region)


def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    """
    Publish a domain event to the SQS notification queue.

    Silently skips (logs at DEBUG) when SQS_QUEUE_URL is not configured.
    This keeps local development and test runs clean — no mocking required
    in tests that don't specifically test event publishing.

    Catches and logs all exceptions — never propagates them to the caller.
    """
    if not settings.sqs_queue_url:
        logger.debug("SQS_QUEUE_URL not set — skipping event: %s", event_type)
        return

    message: dict[str, Any] = {
        "event_type": event_type,
        "payload": payload,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "version": "1.0",
    }

    try:
        client = _sqs_client()
        client.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=json.dumps(message),
        )
        logger.info("Published event '%s'", event_type)
    except Exception:
        logger.exception(
            "Failed to publish event '%s' — notification will be missed", event_type
        )
