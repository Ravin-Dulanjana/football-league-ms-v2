"""
Tests for app/middleware/request_id.py and app/middleware/logging.py.

Tests 1-7 of the Phase 7 observability suite.

Design:
  - All tests use the shared `client` fixture from conftest.py.
  - caplog is used to capture structured log records WITHOUT relying on
    propagation. We use `caplog.at_level(level, logger=name)` which installs
    caplog's handler directly on the named logger — this works even when
    the logger has propagate=False (which get_logger() sets to avoid
    duplicate output in production).
  - Metrics are NOT tested here — see test_metrics.py.
"""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Test 1: X-Request-ID is added to every response
# ---------------------------------------------------------------------------


def test_request_id_is_added_to_response(client: TestClient) -> None:
    """
    Every response must carry an X-Request-ID header.

    This allows a client to say "my request ID is X-Request-ID: abc123"
    and correlate it with the server-side log entry that has the same field.
    """
    response = client.get("/clubs/")
    assert "X-Request-ID" in response.headers, (
        "Response must include X-Request-ID header for client-side correlation"
    )


# ---------------------------------------------------------------------------
# Test 2: X-Request-ID in response matches the one sent by the client
# ---------------------------------------------------------------------------


def test_request_id_is_preserved_if_client_sends_one(client: TestClient) -> None:
    """
    If the client supplies X-Request-ID, the same value must be echoed back.

    This enables distributed tracing: an upstream gateway assigns an ID and
    passes it to every downstream service — all services echo it back so logs
    across services can be joined by ID.
    """
    client_id = "my-trace-id-abc123"
    response = client.get("/clubs/", headers={"X-Request-ID": client_id})
    assert response.headers["X-Request-ID"] == client_id


# ---------------------------------------------------------------------------
# Test 3: Server generates a UUID when client doesn't send X-Request-ID
# ---------------------------------------------------------------------------


def test_request_id_is_valid_uuid_when_generated(client: TestClient) -> None:
    """
    When the client doesn't provide X-Request-ID, the server must generate
    a valid UUID4 (not an empty string, not a fixed value).
    """
    response = client.get("/clubs/")
    req_id = response.headers.get("X-Request-ID", "")
    try:
        parsed = uuid.UUID(req_id, version=4)
        assert str(parsed) == req_id.lower(), "Generated ID must be a valid UUID4"
    except ValueError:
        pytest.fail(f"X-Request-ID '{req_id}' is not a valid UUID4")


# ---------------------------------------------------------------------------
# Test 4: Middleware emits one log record per request (JSON-compatible dict)
# ---------------------------------------------------------------------------


def test_logging_middleware_emits_one_record_per_request(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """
    LoggingMiddleware must emit exactly one log record for each HTTP request.

    The record's msg must be a dict (the raw structured data before the
    JsonFormatter serialises it to a string).
    """
    with caplog.at_level(logging.INFO, logger="app.middleware.logging"):
        client.get("/clubs/")

    http_records = [
        r
        for r in caplog.records
        if isinstance(r.msg, dict) and r.msg.get("event") == "http_request"
    ]
    assert len(http_records) == 1, (
        "Expected exactly one http_request log record per GET /clubs/ request"
    )


# ---------------------------------------------------------------------------
# Test 5: Log record includes method, path, and status_code
# ---------------------------------------------------------------------------


def test_logging_middleware_logs_method_path_status(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """
    The http_request log record must contain: event, method, path, status_code.

    These are the minimum fields needed to answer "what request was this?"
    """
    with caplog.at_level(logging.INFO, logger="app.middleware.logging"):
        client.get("/clubs/")

    record = next(
        r
        for r in caplog.records
        if isinstance(r.msg, dict) and r.msg.get("event") == "http_request"
    )
    log = record.msg
    assert log["method"] == "GET"
    assert log["path"] == "/clubs/"
    assert isinstance(log["status_code"], int)
    assert log["status_code"] == 200


# ---------------------------------------------------------------------------
# Test 6: Log record includes duration_ms as a positive number
# ---------------------------------------------------------------------------


def test_logging_middleware_logs_duration_ms(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """
    duration_ms must be present and be a positive float.

    This is the raw latency datapoint used to compute p50/p95/p99 in
    CloudWatch (or any other metric backend).
    """
    with caplog.at_level(logging.INFO, logger="app.middleware.logging"):
        client.get("/clubs/")

    record = next(
        r
        for r in caplog.records
        if isinstance(r.msg, dict) and r.msg.get("event") == "http_request"
    )
    duration = record.msg.get("duration_ms")
    assert duration is not None, "duration_ms must be present in the log record"
    assert isinstance(duration, float | int), "duration_ms must be numeric"
    assert duration >= 0, "duration_ms must be non-negative"


# ---------------------------------------------------------------------------
# Test 7: Log record includes request_id matching the response header
# ---------------------------------------------------------------------------


def test_logging_middleware_logs_request_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """
    The request_id in the log record must match the X-Request-ID in the
    response header.

    This is the linkage that lets engineers correlate a client error report
    ("my request ID was abc") with the server log entry.
    """
    with caplog.at_level(logging.INFO, logger="app.middleware.logging"):
        response = client.get("/clubs/")

    expected_id = response.headers.get("X-Request-ID", "")
    record = next(
        r
        for r in caplog.records
        if isinstance(r.msg, dict) and r.msg.get("event") == "http_request"
    )
    assert record.msg.get("request_id") == expected_id, (
        "request_id in log must match X-Request-ID response header"
    )
