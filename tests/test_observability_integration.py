"""
Integration tests that verify the full observability stack (middleware + metrics)
works end-to-end for a real HTTP request through the FastAPI app.

Tests 17-18 of the Phase 7 observability suite.

These tests are broader than the unit tests in test_middleware.py and
test_metrics.py — they exercise both the request-ID middleware AND the
logging middleware in one pass, and verify that a real (mocked) metric
payload is published with the correct fields.

Design:
  - boto3 is mocked so no real AWS calls happen.
  - CLOUDWATCH_NAMESPACE is monkeypatched to "TestNamespace" to enable
    metric publishing for the duration of the test.
  - Both caplog and mock.patch are used together.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.middleware.logging as logging_module

# ---------------------------------------------------------------------------
# Test 17: A successful request produces a log record AND publishes a metric
# ---------------------------------------------------------------------------


def test_successful_request_produces_log_and_metric(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A single GET /clubs/ request must produce:
      1. One http_request log record with method="GET", path="/clubs/", status_code=200
      2. One put_metric_data call with RequestCount and RequestDuration metrics
         (but NOT ErrorCount since status is 200).

    This test confirms that both observability channels fire on the same request.
    """
    ns = "TestNamespace"
    monkeypatch.setattr(logging_module.settings, "cloudwatch_namespace", ns)
    monkeypatch.setattr(logging_module, "_METRIC_NAMESPACE", ns)

    mock_cw = MagicMock()

    with caplog.at_level(logging.INFO, logger="app.middleware.logging"):
        with patch("app.middleware.logging.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_cw
            response = client.get("/clubs/")

    assert response.status_code == 200

    # --- Log assertion ---
    http_records = [
        r
        for r in caplog.records
        if isinstance(r.msg, dict) and r.msg.get("event") == "http_request"
    ]
    assert len(http_records) == 1
    log = http_records[0].msg
    assert log["method"] == "GET"
    assert log["path"] == "/clubs/"
    assert log["status_code"] == 200
    assert "duration_ms" in log
    assert "request_id" in log

    # --- Metric assertion ---
    mock_cw.put_metric_data.assert_called_once()
    call_kwargs = mock_cw.put_metric_data.call_args[1]
    assert call_kwargs["Namespace"] == ns
    metric_names = [m["MetricName"] for m in call_kwargs["MetricData"]]
    assert "RequestCount" in metric_names
    assert "RequestDuration" in metric_names
    assert "ErrorCount" not in metric_names  # 200 is not an error


# ---------------------------------------------------------------------------
# Test 18: A 5xx response increments ErrorCount in the metrics payload
# ---------------------------------------------------------------------------


def test_5xx_response_produces_error_count_metric(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    When an unhandled exception occurs inside a route handler, LoggingMiddleware
    must catch it, publish ErrorCount, then re-raise so ServerErrorMiddleware
    can return a 500 response to the client.

    Starlette's ServerErrorMiddleware always re-raises the exception after
    generating the 500 response (by design — it lets test clients and servers
    log the error). TestClient re-raises it too when raise_server_exceptions=True.
    We use pytest.raises to consume the re-raised exception so the test can
    verify the metric was published.

    Why this matters: the error-rate alarm is `ErrorCount / RequestCount > 0.01`.
    If ErrorCount is never published on 5xx, the alarm can never fire.
    """
    ns = "TestNamespace"
    monkeypatch.setattr(logging_module.settings, "cloudwatch_namespace", ns)
    monkeypatch.setattr(logging_module, "_METRIC_NAMESPACE", ns)

    mock_cw = MagicMock()

    with patch("app.middleware.logging.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_cw
        with patch("app.services.club_service.get_all_clubs") as mock_service:
            mock_service.side_effect = RuntimeError("Database connection failed")
            with caplog.at_level(logging.ERROR, logger="app.middleware.logging"):
                # ServerErrorMiddleware re-raises the exception after returning 500;
                # TestClient propagates it. Consume it here so we can check metrics.
                with pytest.raises((RuntimeError, Exception)):
                    client.get("/clubs/")

    # --- Metric assertion ---
    # LoggingMiddleware's exception handler must have published metrics
    # BEFORE re-raising, so put_metric_data should have been called.
    mock_cw.put_metric_data.assert_called_once()
    metric_data = mock_cw.put_metric_data.call_args[1]["MetricData"]
    metric_names = [m["MetricName"] for m in metric_data]
    assert "ErrorCount" in metric_names, (
        "ErrorCount metric must be published when the middleware catches "
        "a 5xx exception"
    )
    error_metric = next(m for m in metric_data if m["MetricName"] == "ErrorCount")
    assert error_metric["Value"] == 1.0
