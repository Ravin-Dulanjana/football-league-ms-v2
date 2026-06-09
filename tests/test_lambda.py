"""
Tests for structured logging in infra/lambda/notification_handler.py.

Tests 15-16 of the Phase 7 observability suite.

These tests verify that the Lambda handler emits structured JSON log records —
not just that it processes messages correctly (that's tested in test_lambda_handler.py).

Design:
  - boto3 (SES) is mocked so no real emails are sent.
  - caplog captures records from the Lambda's logger directly.
  - We check that specific structured fields are present in the log records.
"""

from __future__ import annotations

import importlib
import json
import logging
import sys
from typing import Any
from unittest.mock import patch

import pytest

# `lambda` is a Python keyword — we can't use `from infra.lambda import ...`.
# Use importlib to load the module by its file path instead.
_spec = importlib.util.spec_from_file_location(  # type: ignore[attr-defined]
    "notification_handler",
    "infra/lambda/notification_handler.py",
)
handler_module = importlib.util.module_from_spec(_spec)  # type: ignore[attr-defined]
_spec.loader.exec_module(handler_module)
sys.modules["notification_handler"] = handler_module
handler = handler_module.handler


def _make_sqs_event(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a minimal SQS event dict for the Lambda handler."""
    return {
        "Records": [
            {
                "messageId": f"msg-{i}",
                "body": json.dumps(rec),
            }
            for i, rec in enumerate(records)
        ]
    }


_VALID_MESSAGE = {
    "event_type": "release.confirmed",
    "payload": {
        "release_id": 42,
        "player_name": "Kamal Perera",
        "club_name": "Wattala SC",
        "recipient_email": "admin@wattalasc.com",
    },
    "timestamp": "2025-01-15T10:00:00Z",
    "version": "1.0",
}


# ---------------------------------------------------------------------------
# Test 15: Successful Lambda invocation logs structured JSON
# ---------------------------------------------------------------------------


def test_lambda_logs_structured_json_on_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    On successful message processing, the Lambda handler must log:
      1. lambda.invocation.start with batch_size
      2. notification.sent with event_type, recipient, success=True, duration_ms
      3. lambda.invocation.complete with batch_size and failures=0
    All records must have dict msg (structured JSON).
    """
    event = _make_sqs_event([_VALID_MESSAGE])

    with caplog.at_level(logging.INFO, logger=handler_module.logger.name):
        with patch.object(handler_module, "_send_email") as mock_send:
            mock_send.return_value = None
            result = handler(event, {})

    assert result == {"batchItemFailures": []}

    # Check for the three expected structured log records
    dicts = [r.msg for r in caplog.records if isinstance(r.msg, dict)]

    start_events = [d for d in dicts if d.get("event") == "lambda.invocation.start"]
    assert len(start_events) == 1
    assert start_events[0]["batch_size"] == 1

    sent_events = [d for d in dicts if d.get("event") == "notification.sent"]
    assert len(sent_events) == 1
    assert sent_events[0]["event_type"] == "release.confirmed"
    assert sent_events[0]["recipient"] == "admin@wattalasc.com"
    assert sent_events[0]["success"] is True
    assert "duration_ms" in sent_events[0]

    complete_events = [
        d for d in dicts if d.get("event") == "lambda.invocation.complete"
    ]
    assert len(complete_events) == 1
    assert complete_events[0]["failures"] == 0


# ---------------------------------------------------------------------------
# Test 16: Failed Lambda invocation logs structured JSON with error details
# ---------------------------------------------------------------------------


def test_lambda_logs_structured_json_on_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    When _send_email raises, the handler must:
      1. Log notification.error with error_type, message, success=False
      2. Include the failed message in batchItemFailures (SQS will retry)
      3. Log lambda.invocation.complete with failures=1
    All records must have dict msg (structured JSON).
    """
    event = _make_sqs_event([_VALID_MESSAGE])

    with caplog.at_level(logging.ERROR, logger=handler_module.logger.name):
        with patch.object(handler_module, "_send_email") as mock_send:
            mock_send.side_effect = RuntimeError("SES connection timeout")
            result = handler(event, {})

    assert len(result["batchItemFailures"]) == 1
    assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-0"

    dicts = [r.msg for r in caplog.records if isinstance(r.msg, dict)]

    error_events = [d for d in dicts if d.get("event") == "notification.error"]
    assert len(error_events) == 1
    assert error_events[0]["error_type"] == "RuntimeError"
    assert "SES connection timeout" in error_events[0]["message"]
    assert error_events[0]["success"] is False
    assert error_events[0]["message_id"] == "msg-0"
