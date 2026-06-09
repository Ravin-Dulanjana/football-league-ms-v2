"""
Unit tests for infra/lambda/notification_handler.py.

The Lambda handler is NOT an installable Python package (it's in infra/lambda/,
and 'lambda' is a Python keyword so cannot be imported via normal paths).
We use importlib.util.spec_from_file_location to load it directly.

Test design:
  - boto3 SES calls are always mocked — no real AWS calls.
  - Tests exercise: happy path, SES failure (DLQ path), unknown event_type,
    missing recipient, and partial batch failure.
"""

from __future__ import annotations

import importlib.util
import json
import os
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Load the Lambda handler module from infra/lambda/notification_handler.py.
#
# We can't do `from infra.lambda.notification_handler import handler`
# because 'lambda' is a Python keyword. Instead we load by file path.
# ---------------------------------------------------------------------------
_HANDLER_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__), "..", "infra", "lambda", "notification_handler.py"
    )
)

_spec = importlib.util.spec_from_file_location("notification_handler", _HANDLER_PATH)
assert _spec is not None, f"Could not load spec from {_HANDLER_PATH}"
notification_handler: ModuleType = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(notification_handler)  # type: ignore[union-attr]

# Convenience aliases
handler = notification_handler.handler
_process_message = notification_handler._process_message  # noqa: SLF001


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sqs_event(*messages: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal SQS event dict with the given message bodies."""
    return {
        "Records": [
            {
                "messageId": f"msg-{i}",
                "body": json.dumps(msg),
            }
            for i, msg in enumerate(messages)
        ]
    }


def _registration_accepted_message(
    player_name: str = "Kamal Perera",
    club_name: str = "Wattala SC",
    season_name: str = "2025 Season",
    recipient: str = "admin@wattalasc.com",
) -> dict[str, Any]:
    return {
        "event_type": "registration.accepted",
        "payload": {
            "registration_request_id": 1,
            "player_name": player_name,
            "club_name": club_name,
            "season_name": season_name,
            "recipient_email": recipient,
        },
        "timestamp": "2026-06-09T10:00:00+00:00",
        "version": "1.0",
    }


# ---------------------------------------------------------------------------
# Tests — happy path
# ---------------------------------------------------------------------------


def test_handler_sends_email_for_registration_accepted() -> None:
    """
    Happy path: handler processes a registration.accepted message and calls
    SES send_email with the correct recipient and subject.
    """
    event = _make_sqs_event(_registration_accepted_message())

    with patch.object(notification_handler, "boto3") as mock_boto3:
        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses

        result = handler(event, None)

    assert result == {"batchItemFailures": []}
    mock_ses.send_email.assert_called_once()

    call_kwargs = mock_ses.send_email.call_args[1]
    assert call_kwargs["Destination"]["ToAddresses"] == ["admin@wattalasc.com"]
    assert "Kamal Perera" in call_kwargs["Message"]["Subject"]["Data"]
    assert "accepted" in call_kwargs["Message"]["Subject"]["Data"].lower()


# ---------------------------------------------------------------------------
# Tests — DLQ path
# ---------------------------------------------------------------------------


def test_handler_returns_batch_failure_when_ses_raises() -> None:
    """
    DLQ path: when SES raises (e.g. throttle, sandbox recipient not verified),
    the handler returns that message ID in batchItemFailures rather than
    raising. SQS will re-deliver only that message after the visibility
    timeout. After max_receive_count=3 retries, SQS moves it to the DLQ.
    """
    event = _make_sqs_event(_registration_accepted_message())

    with patch.object(notification_handler, "boto3") as mock_boto3:
        mock_ses = MagicMock()
        mock_ses.send_email.side_effect = RuntimeError("SES throttled")
        mock_boto3.client.return_value = mock_ses

        result = handler(event, None)

    # Message-0 failed — reported as a batch item failure
    assert result == {"batchItemFailures": [{"itemIdentifier": "msg-0"}]}


# ---------------------------------------------------------------------------
# Tests — discard cases (no retry needed)
# ---------------------------------------------------------------------------


def test_handler_skips_unknown_event_type() -> None:
    """
    An unrecognised event_type is silently discarded — no SES call, no
    batch failure. Retrying wouldn't help since the handler would always
    skip it; moving to DLQ would just accumulate junk.
    """
    event = _make_sqs_event(
        {
            "event_type": "season.created",  # not in _TEMPLATES
            "payload": {"recipient_email": "admin@example.com"},
        }
    )

    with patch.object(notification_handler, "boto3") as mock_boto3:
        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses

        result = handler(event, None)

    assert result == {"batchItemFailures": []}
    mock_ses.send_email.assert_not_called()


def test_handler_skips_missing_recipient_email() -> None:
    """
    A message with no recipient_email (e.g. club has no email address) is
    silently discarded — no SES call, no batch failure.
    """
    event = _make_sqs_event(
        {
            "event_type": "registration.accepted",
            "payload": {
                "player_name": "Kamal",
                "club_name": "Wattala SC",
                "season_name": "2025 Season",
                # recipient_email is deliberately absent
            },
        }
    )

    with patch.object(notification_handler, "boto3") as mock_boto3:
        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses

        result = handler(event, None)

    assert result == {"batchItemFailures": []}
    mock_ses.send_email.assert_not_called()


# ---------------------------------------------------------------------------
# Tests — partial batch failure
# ---------------------------------------------------------------------------


def test_handler_partial_batch_failure() -> None:
    """
    With two messages in a batch where SES succeeds for the first but raises
    for the second, only the second message ID appears in batchItemFailures.
    The first message is NOT retried (no duplicate email).
    """
    msg_ok = _registration_accepted_message(recipient="ok@example.com")
    msg_fail = _registration_accepted_message(recipient="fail@example.com")
    event = _make_sqs_event(msg_ok, msg_fail)

    call_count = 0

    def fake_send_email(**kwargs: Any) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("SES error on second message")

    with patch.object(notification_handler, "boto3") as mock_boto3:
        mock_ses = MagicMock()
        mock_ses.send_email.side_effect = fake_send_email
        mock_boto3.client.return_value = mock_ses

        result = handler(event, None)

    # Only msg-1 (second message) failed
    assert result == {"batchItemFailures": [{"itemIdentifier": "msg-1"}]}
    assert mock_ses.send_email.call_count == 2
