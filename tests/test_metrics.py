"""
Tests for the CloudWatch metric publisher in app/middleware/logging.py.

Tests 8-11 of the Phase 7 observability suite.

Design:
  - _publish_metrics is tested directly (unit tests), not through HTTP.
  - boto3 is patched at the import location (app.middleware.logging.boto3)
    so no real AWS calls are made.
  - CLOUDWATCH_NAMESPACE is monkeypatched via pytest's monkeypatch fixture
    so we don't touch the real settings singleton.

Why test _publish_metrics directly and not via the middleware?
  Testing through HTTP would require setting CLOUDWATCH_NAMESPACE AND
  patching boto3 AND checking the mock after the response — three moving
  parts. Testing _publish_metrics directly is simpler and just as meaningful
  since the function is a pure callable with clear inputs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import app.middleware.logging as logging_module
from app.middleware.logging import _publish_metrics

# ---------------------------------------------------------------------------
# Test 8: No metric published when CLOUDWATCH_NAMESPACE is empty
# ---------------------------------------------------------------------------


def test_publish_metrics_skips_when_no_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    When CLOUDWATCH_NAMESPACE is empty (local dev / tests default),
    boto3 must never be called. This prevents spurious errors when
    running locally without AWS credentials.
    """
    monkeypatch.setattr(logging_module.settings, "cloudwatch_namespace", "")
    # Also patch the module-level cached namespace so the change takes effect
    monkeypatch.setattr(logging_module, "_METRIC_NAMESPACE", "")

    with patch("app.middleware.logging.boto3") as mock_boto3:
        _publish_metrics("/clubs/", 42.0, 200)
        mock_boto3.client.assert_not_called()


# ---------------------------------------------------------------------------
# Test 9: put_metric_data is called when namespace is set
# ---------------------------------------------------------------------------


def test_publish_metrics_calls_put_metric_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    When CLOUDWATCH_NAMESPACE is set, _publish_metrics must call
    cloudwatch.put_metric_data with the correct namespace.
    """
    ns = "FootballLeague"
    monkeypatch.setattr(logging_module.settings, "cloudwatch_namespace", ns)
    monkeypatch.setattr(logging_module, "_METRIC_NAMESPACE", ns)

    mock_cw = MagicMock()
    with patch("app.middleware.logging.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_cw
        _publish_metrics("/releases/", 87.3, 201)

    mock_boto3.client.assert_called_once_with(
        "cloudwatch", region_name="ap-southeast-1"
    )
    mock_cw.put_metric_data.assert_called_once()

    call_kwargs = mock_cw.put_metric_data.call_args[1]
    assert call_kwargs["Namespace"] == ns


# ---------------------------------------------------------------------------
# Test 10: ErrorCount metric is included on 5xx responses
# ---------------------------------------------------------------------------


def test_publish_metrics_includes_error_count_on_5xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    For 5xx responses, the payload must include an ErrorCount metric with
    value 1 and unit "Count". This is what the error-rate alarm uses.
    """
    ns = "FootballLeague"
    monkeypatch.setattr(logging_module.settings, "cloudwatch_namespace", ns)
    monkeypatch.setattr(logging_module, "_METRIC_NAMESPACE", ns)

    mock_cw = MagicMock()
    with patch("app.middleware.logging.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_cw
        _publish_metrics("/clubs/", 200.0, 500)

    metric_data = mock_cw.put_metric_data.call_args[1]["MetricData"]
    metric_names = [m["MetricName"] for m in metric_data]

    assert "ErrorCount" in metric_names, (
        "5xx responses must publish an ErrorCount metric"
    )
    error_metric = next(m for m in metric_data if m["MetricName"] == "ErrorCount")
    assert error_metric["Value"] == 1.0
    assert error_metric["Unit"] == "Count"


# ---------------------------------------------------------------------------
# Test 11: ErrorCount metric is NOT included on 2xx/4xx responses
# ---------------------------------------------------------------------------


def test_publish_metrics_no_error_count_on_2xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    For 2xx and 4xx responses, ErrorCount must not be published.

    4xx (client errors) are excluded because they represent invalid client
    requests, not server failures. Including 4xx in the error rate would
    alarm on legitimate auth failures (401s are expected on bad tokens).

    Only 5xx (unexpected server errors) are server-side failures that
    should appear in the error rate SLO.
    """
    ns = "FootballLeague"
    monkeypatch.setattr(logging_module.settings, "cloudwatch_namespace", ns)
    monkeypatch.setattr(logging_module, "_METRIC_NAMESPACE", ns)

    mock_cw = MagicMock()
    with patch("app.middleware.logging.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_cw

        # 200 OK
        _publish_metrics("/clubs/", 50.0, 200)
        metric_data_200 = mock_cw.put_metric_data.call_args[1]["MetricData"]
        assert "ErrorCount" not in [m["MetricName"] for m in metric_data_200]

        mock_cw.reset_mock()

        # 401 Unauthorized
        _publish_metrics("/clubs/", 10.0, 401)
        metric_data_401 = mock_cw.put_metric_data.call_args[1]["MetricData"]
        assert "ErrorCount" not in [m["MetricName"] for m in metric_data_401]
