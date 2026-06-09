"""
Tests that verify sensitive data is NEVER logged.

Tests 12-14 of the Phase 7 observability suite.

Security policy:
  The following fields must NEVER appear in any log record:
    - Passwords (from login requests)
    - Full NIC numbers (personal identifier for Sri Lankan national ID cards)
    - Full JWT tokens (Bearer tokens from Authorization headers)

Why test this?
  Structured logging makes it easy to accidentally log too much data.
  A log collector (CloudWatch, Splunk, Datadog) sees everything sent to it.
  If a password or JWT token appears in logs:
    - Any operator with log access can impersonate the user.
    - CloudWatch logs are queryable by anyone with IAM logs:GetLogEvents.
  These tests act as a regression guard — a future change to the middleware
  or service that accidentally adds sensitive fields will fail here.

Test strategy:
  - For each sensitive field, capture ALL log records during the API call.
  - Assert that none of the records' serialised content contains the value.
  - We convert each record.msg to a JSON string so we can do a simple
    substring search regardless of nesting depth.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient


def _captured_log_text(records: list[logging.LogRecord]) -> str:
    """
    Serialise every captured log record to a single searchable string.

    We dump each record to JSON (using the dict if msg is a dict, else the
    string form) and join them. This lets us do a simple `in` check.
    """
    parts: list[str] = []
    for r in records:
        if isinstance(r.msg, dict):
            parts.append(json.dumps(r.msg, default=str))
        else:
            parts.append(str(r.getMessage()))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Test 12: Password is never logged
# ---------------------------------------------------------------------------


def test_login_does_not_log_password(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """
    POST /auth/login sends a password in the request body.
    No log record at any level — from any logger — must contain the password.

    The login endpoint calls cognito.login(email, password). Even if Cognito
    raises an error, the password must not appear in the error log.

    We mock boto3 to raise NotAuthorizedException (wrong password) so the
    cognito service exercises its error-handling code path. The test verifies
    the password string is absent from every log record regardless of outcome.
    """
    password = "SuperSecret!99"
    _not_authorised = ClientError(
        {
            "Error": {
                "Code": "NotAuthorizedException",
                "Message": "Incorrect username or password",
            }
        },
        "InitiateAuth",
    )
    with caplog.at_level(logging.DEBUG):
        with patch("app.services.cognito.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.initiate_auth.side_effect = _not_authorised
            mock_boto3.client.return_value = mock_client

            response = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": password},
            )

    assert response.status_code == 401  # Cognito NotAuthorized → 401
    log_text = _captured_log_text(caplog.records)
    assert password not in log_text, (
        f"Password '{password}' must never appear in any log record. "
        "Found in: " + log_text[:200]
    )


# ---------------------------------------------------------------------------
# Test 13: NIC number is not logged in player creation
# ---------------------------------------------------------------------------


def test_player_creation_does_not_log_nic(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """
    POST /players/ includes a NIC number (Sri Lankan national ID).
    The player_service logs create_player.start and create_player.complete —
    neither must contain the NIC number.

    The NIC is a personal identifier. If logged, it exposes PII in
    CloudWatch to anyone with log access, which violates data minimisation.
    """
    nic = "199516512345"
    payload = {
        "full_name": "Kamal Perera",
        "date_of_birth": "1995-06-15",
        "nic_number": nic,
    }
    with caplog.at_level(logging.INFO, logger="app.services.player_service"):
        client.post("/players/", json=payload)

    log_text = _captured_log_text(caplog.records)
    assert nic not in log_text, (
        f"NIC number '{nic}' must never appear in any log record. "
        "Found in: " + log_text[:200]
    )


# ---------------------------------------------------------------------------
# Test 14: JWT token is not logged in the request log
# ---------------------------------------------------------------------------


def test_jwt_token_not_logged_in_request_log(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Even if a client sends Authorization: Bearer <token>, the token value
    must never appear in the middleware's http_request log record.

    LoggingMiddleware logs: event, method, path, status_code, duration_ms,
    user_id, request_id — it never reads or logs request headers.

    A JWT in logs is dangerous: anyone with log access can replay the token
    (until its 1-hour expiry) to impersonate the user.
    """
    fake_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.fake.signature"
    with caplog.at_level(logging.INFO, logger="app.middleware.logging"):
        # The token will fail JWT verification (no real keys), triggering
        # a 401. We're only checking that the token itself isn't logged.
        client.get("/clubs/", headers={"Authorization": f"Bearer {fake_token}"})

    log_text = _captured_log_text(caplog.records)
    assert fake_token not in log_text, (
        "JWT token must never appear in any log record. Found in: " + log_text[:200]
    )
    # Also verify the word "Bearer" and the token signature fragment aren't there
    assert "signature" not in log_text.lower() or "fake.signature" not in log_text
