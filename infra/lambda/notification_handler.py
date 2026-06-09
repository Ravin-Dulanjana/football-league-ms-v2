"""
Football League MS — SQS notification handler (Lambda).

Triggered by SQS events. For each message, parses the event_type and
payload, builds an email, and sends it via SES.

Uses ReportBatchItemFailures: individual messages that fail are returned
in the response so SQS retries only them — not the entire batch. This
prevents duplicate sends for messages that already succeeded.

Retry flow:
  1. SES call raises an exception.
  2. handler() catches it, adds the message ID to batchItemFailures.
  3. SQS re-delivers that specific message after the visibility timeout.
  4. After max_receive_count failures (3), SQS moves it to the DLQ.

Environment variables set by CDK:
  SES_SENDER_EMAIL — verified sender address in SES
  SES_REGION       — AWS region where the SES identity is verified
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import boto3

# ---------------------------------------------------------------------------
# Structured JSON logger for Lambda.
#
# Lambda captures stdout/stderr and ships each line to CloudWatch Logs
# automatically (group /aws/lambda/<function-name>).
#
# By emitting one JSON object per line, CloudWatch Logs Insights can query
# individual fields:
#   fields event_type, recipient, success, duration_ms
#   | filter success = false
#   | sort @timestamp desc
#
# ⚠️  NEVER log passwords, full JWT tokens, or NIC numbers here.
#     SES recipient email addresses ARE safe to log (they are already in
#     the CloudWatch group scoped to this Lambda function, not the API logs).
# ---------------------------------------------------------------------------


class _JsonFormatter(logging.Formatter):
    """Render LogRecord as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
        }
        if isinstance(record.msg, dict):
            data.update(record.msg)
        else:
            data["message"] = record.getMessage()
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(_handler)
# propagate=True (default) so pytest's caplog can capture records.
# In Lambda, the root logger has no handlers by default so there are no
# duplicate lines.

SES_SENDER_EMAIL: str = os.environ.get("SES_SENDER_EMAIL", "")
SES_REGION: str = os.environ.get("SES_REGION", "ap-southeast-1")

# ---------------------------------------------------------------------------
# Email templates
#
# Keys must exactly match the event_type strings published by events.py.
# Placeholders are filled from payload fields via str.format(**payload).
# Unknown placeholders raise KeyError → message goes to batchItemFailures.
# ---------------------------------------------------------------------------
_TEMPLATES: dict[str, dict[str, str]] = {
    "registration.requested": {
        "subject": "New registration request — {player_name} for {season_name}",
        "body": (
            "A new player registration request has been submitted.\n\n"
            "Player: {player_name}\n"
            "Club:   {club_name}\n"
            "Season: {season_name}\n\n"
            "Log in to the Football League system to review and accept or reject."
        ),
    },
    "registration.accepted": {
        "subject": "{player_name} accepted registration — {season_name}",
        "body": (
            "The player has accepted their registration request.\n\n"
            "Player: {player_name}\n"
            "Club:   {club_name}\n"
            "Season: {season_name}\n"
        ),
    },
    "registration.rejected": {
        "subject": "{player_name} declined registration — {season_name}",
        "body": (
            "The player has rejected their registration request.\n\n"
            "Player: {player_name}\n"
            "Club:   {club_name}\n"
            "Season: {season_name}\n"
        ),
    },
    "release.initiated": {
        "subject": "Release initiated — {player_name}",
        "body": (
            "A release request has been submitted for the following player.\n\n"
            "Player: {player_name}\n"
            "Club:   {club_name}\n\n"
            "The player will be prompted to confirm or reject the release."
        ),
    },
    "release.confirmed": {
        "subject": "{player_name} confirmed their release",
        "body": (
            "The player has confirmed their release.\n\n"
            "Player: {player_name}\n"
            "Club:   {club_name}\n"
        ),
    },
}


def _ses_client() -> Any:
    return boto3.client("ses", region_name=SES_REGION)


def _send_email(recipient: str, subject: str, body: str) -> None:
    """
    Send a plain-text email via SES.

    Raises on failure (e.g. throttle, unverified recipient in sandbox mode).
    The caller catches and reports a batch item failure so SQS retries.
    """
    client = _ses_client()
    client.send_email(
        Source=SES_SENDER_EMAIL,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
        },
    )


def _process_message(body: dict[str, Any]) -> None:
    """
    Process one decoded SQS message body.

    Raises on any error — the caller catches and marks the message as failed.
    Two cases are silently skipped (no retry needed — they're logic errors):
      - Unknown event_type  → log + return (retrying won't fix it)
      - Missing recipient   → log + return (retrying won't fix it)
    """
    event_type: str = body.get("event_type", "")
    payload: dict[str, Any] = body.get("payload", {})

    template = _TEMPLATES.get(event_type)
    if template is None:
        logger.warning(
            {"event": "notification.unknown_event_type", "event_type": event_type}
        )
        return

    recipient = payload.get("recipient_email")
    if not recipient:
        logger.warning(
            {
                "event": "notification.missing_recipient",
                "event_type": event_type,
            }
        )
        return

    start = time.monotonic()
    subject = template["subject"].format(**payload)
    body_text = template["body"].format(**payload)
    _send_email(str(recipient), subject, body_text)
    duration_ms = round((time.monotonic() - start) * 1000, 2)

    logger.info(
        {
            "event": "notification.sent",
            "event_type": event_type,
            "recipient": str(recipient),
            "success": True,
            "duration_ms": duration_ms,
        }
    )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    SQS batch handler with partial failure reporting (ReportBatchItemFailures).

    Returns {"batchItemFailures": [...]} for messages that could not be
    processed. SQS will re-deliver only those messages after the visibility
    timeout expires. After max_receive_count retries, the message is moved
    to the dead letter queue automatically.
    """
    records = event.get("Records", [])
    logger.info(
        {
            "event": "lambda.invocation.start",
            "batch_size": len(records),
        }
    )

    batch_item_failures: list[dict[str, str]] = []

    for record in records:
        message_id: str = record["messageId"]
        try:
            body = json.loads(record["body"])
            _process_message(body)
        except Exception as exc:
            logger.error(
                {
                    "event": "notification.error",
                    "message_id": message_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "success": False,
                }
            )
            batch_item_failures.append({"itemIdentifier": message_id})

    logger.info(
        {
            "event": "lambda.invocation.complete",
            "batch_size": len(records),
            "failures": len(batch_item_failures),
        }
    )

    return {"batchItemFailures": batch_item_failures}
