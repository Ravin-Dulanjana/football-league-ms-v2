"""
SQS notification consumer.

Reads domain events from the SQS queue and sends transactional emails via SES.
In-app Notification rows are written synchronously by the service layer inside
the same DB transaction — this worker only handles async email delivery.

Entry points
------------
  EC2 worker (long-polling loop):
      python -m app.workers.sqs_consumer

  AWS Lambda trigger:
      Set handler = app.workers.sqs_consumer.lambda_handler
      in the Lambda function configuration.

Event types handled
-------------------
  club_membership.invited   → email the invited player
  club_membership.accepted  → email the club (player accepted invite)
  club_membership.rejected  → email the club (player declined invite)
  registration.requested    → email the player (squad registration request)
  registration.accepted     → email the club (player acknowledged registration)
  release.confirmed         → email the released player

All handlers skip silently when SES_SENDER_EMAIL is not configured
(keeps local dev clean without mocking boto3).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Email content per event type
# ---------------------------------------------------------------------------

_WFL = "Wattala Football League"

_SUBJECTS: dict[str, str] = {
    "club_membership.invited": f"You've been invited to join a club — {_WFL}",
    "club_membership.accepted": f"A player has joined your club — {_WFL}",
    "club_membership.rejected": f"A player declined your club invite — {_WFL}",
    "registration.requested": f"Squad registration request — {_WFL}",
    "registration.accepted": f"Squad registration acknowledged — {_WFL}",
    "release.confirmed": f"You have been released — {_WFL}",
}


def _build_body(event_type: str, payload: dict[str, Any]) -> tuple[str, str]:
    """Return (plain-text body, HTML body) for the given event."""
    if event_type == "club_membership.invited":
        club = payload.get("club_name", "a club")
        text = (
            f"You have been invited to join {club}.\n\n"
            "Log in to the Wattala Football League portal to accept or decline."
        )
        html = (
            f"<p>You have been invited to join <strong>{club}</strong>.</p>"
            "<p>Log in to the WFL portal to accept or decline the invitation.</p>"
        )

    elif event_type == "club_membership.accepted":
        player = payload.get("player_name", "A player")
        club = payload.get("club_name", "your club")
        text = f"{player} has accepted the invite and joined {club}."
        html = (
            f"<p><strong>{player}</strong> has accepted the invite and joined "
            f"<strong>{club}</strong>.</p>"
        )

    elif event_type == "club_membership.rejected":
        player = payload.get("player_name", "A player")
        club = payload.get("club_name", "your club")
        text = f"{player} has declined the club invite to {club}."
        html = (
            f"<p><strong>{player}</strong> has declined the club invite to "
            f"<strong>{club}</strong>.</p>"
        )

    elif event_type == "registration.requested":
        club = payload.get("club_name", "your club")
        season = payload.get("season_name", "the current season")
        text = (
            f"You have been added to {club}'s squad for {season}.\n\n"
            "Log in to the WFL portal to acknowledge your registration."
        )
        html = (
            f"<p>You have been added to <strong>{club}</strong>'s squad for "
            f"<strong>{season}</strong>.</p>"
            "<p>Log in to the WFL portal to acknowledge your registration.</p>"
        )

    elif event_type == "registration.accepted":
        player = payload.get("player_name", "A player")
        club = payload.get("club_name", "your club")
        season = payload.get("season_name", "the current season")
        text = (
            f"{player} has acknowledged their squad registration for "
            f"{club} in {season}."
        )
        html = (
            f"<p><strong>{player}</strong> has acknowledged their squad "
            f"registration for <strong>{club}</strong> in "
            f"<strong>{season}</strong>.</p>"
        )

    elif event_type == "release.confirmed":
        club = payload.get("club_name", "your club")
        text = (
            f"You have been released from {club}.\n\n"
            "You are now a free player and can receive club invites."
        )
        html = (
            f"<p>You have been released from <strong>{club}</strong>.</p>"
            "<p>You are now a free player and can receive club invites.</p>"
        )

    else:
        text = f"Wattala Football League event: {event_type}"
        html = f"<p>Wattala Football League event: {event_type}</p>"

    return text, html


# ---------------------------------------------------------------------------
# SES email sender
# ---------------------------------------------------------------------------


def _send_email(recipient: str, event_type: str, payload: dict[str, Any]) -> None:
    """Send one SES email. Raises on failure so the caller can handle retries."""
    if not settings.ses_sender_email:
        logger.debug(
            "SES_SENDER_EMAIL not configured — skipping email for %s", event_type
        )
        return

    subject = _SUBJECTS.get(event_type, f"Wattala Football League — {event_type}")
    text_body, html_body = _build_body(event_type, payload)

    ses = boto3.client("ses", region_name=settings.aws_region)
    ses.send_email(
        Source=settings.ses_sender_email,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text_body, "Charset": "UTF-8"},
                "Html": {"Data": html_body, "Charset": "UTF-8"},
            },
        },
    )
    logger.info("Email sent  event='%s'  to=%s", event_type, recipient)


# ---------------------------------------------------------------------------
# Message processor
# ---------------------------------------------------------------------------


def process_message(body: str) -> None:
    """
    Parse and handle one SQS message body string.

    Raises on unrecoverable errors so the caller can leave the message on the
    queue for retry (Lambda partial-batch failure / EC2 no-delete).
    """
    try:
        envelope = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Malformed SQS message (not valid JSON): %.200s", body)
        return  # Poison pill — delete it so it doesn't block the queue forever.

    event_type: str = envelope.get("event_type", "")
    payload: dict[str, Any] = envelope.get("payload", {})
    recipient: str | None = payload.get("recipient_email")

    if not recipient:
        logger.warning("Event '%s' has no recipient_email — skipping email", event_type)
        return

    _send_email(recipient, event_type, payload)


# ---------------------------------------------------------------------------
# AWS Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda entry point triggered by SQS event source mapping.

    Returns batchItemFailures so Lambda retries individual failed messages
    without reprocessing the whole batch.
    """
    records = event.get("Records", [])
    failures: list[dict[str, str]] = []

    for record in records:
        msg_id: str = record.get("messageId", "unknown")
        try:
            process_message(record["body"])
        except ClientError:
            logger.exception("SES error processing message %s", msg_id)
            failures.append({"itemIdentifier": msg_id})
        except Exception:
            logger.exception("Unexpected error processing message %s", msg_id)
            failures.append({"itemIdentifier": msg_id})

    return {"batchItemFailures": failures}


# ---------------------------------------------------------------------------
# EC2 long-polling worker
# ---------------------------------------------------------------------------


def _poll_once(sqs: Any) -> int:
    """Long-poll SQS once, process all returned messages. Returns count processed."""
    response = sqs.receive_message(
        QueueUrl=settings.sqs_queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=20,
        AttributeNames=["All"],
    )
    messages = response.get("Messages", [])
    for msg in messages:
        msg_id = msg.get("MessageId", "?")
        try:
            process_message(msg["Body"])
            sqs.delete_message(
                QueueUrl=settings.sqs_queue_url,
                ReceiptHandle=msg["ReceiptHandle"],
            )
            logger.debug("Deleted message %s", msg_id)
        except Exception:
            logger.exception(
                "Failed to process message %s — leaving on queue for retry", msg_id
            )
    return len(messages)


def run_worker() -> None:
    """Long-polling loop — runs as a systemd service on EC2."""
    if not settings.sqs_queue_url:
        logger.error("SQS_QUEUE_URL not set — worker cannot start")
        sys.exit(1)
    if not settings.ses_sender_email:
        logger.warning("SES_SENDER_EMAIL not set — emails will be skipped silently")

    sqs = boto3.client("sqs", region_name=settings.aws_region)
    logger.info("SQS consumer started — polling %s", settings.sqs_queue_url)

    while True:
        try:
            count = _poll_once(sqs)
            if count:
                logger.info("Processed %d message(s)", count)
        except KeyboardInterrupt:
            logger.info("SQS consumer stopping")
            break
        except Exception:
            logger.exception(
                "Unhandled error in polling loop — will retry on next cycle"
            )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    run_worker()
