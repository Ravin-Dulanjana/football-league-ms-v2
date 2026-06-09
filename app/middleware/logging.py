"""
Structured JSON logging middleware + CloudWatch metric publisher.

Two responsibilities in one module:

1. JsonFormatter / get_logger
   ─────────────────────────
   A logging.Formatter subclass that renders every LogRecord as a single
   JSON object. Services and routers call `get_logger(__name__)` to get
   a logger that emits JSON to stderr.

   Why JSON:
     Plain-text log lines can't be reliably parsed. JSON gives every field
     a name so CloudWatch Logs Insights, Datadog, or any other platform can
     filter by status_code >= 500, group by path, compute avg(duration_ms) —
     no regex required.

2. LoggingMiddleware
   ─────────────────
   Starlette BaseHTTPMiddleware that logs one JSON record per request and
   publishes RequestCount, RequestDuration, and ErrorCount metrics to
   CloudWatch.

   Metrics are only published when CLOUDWATCH_NAMESPACE is set in the
   environment (i.e., on EC2). In local dev and tests the metric call is
   skipped entirely — no mocking required.

   ⚠️  Known limitation:
     Metrics are published synchronously via boto3 on every request. This
     adds ~20-50 ms per request on a cold boto3 session. For high-throughput
     services, batch metrics in a background queue and flush every 60s.
     At football-league traffic levels this is acceptable.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import boto3
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.middleware.request_id import request_id_var

# ---------------------------------------------------------------------------
# JSON formatter + logger factory
# ---------------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """
    Render a LogRecord as a single JSON object.

    If record.msg is a dict, its keys are merged directly into the output
    so callers can write:
        logger.info({"event": "create_club.start", "club_id": 42})
    and get a clean flat JSON line instead of a nested "message" field.

    If record.msg is a string, it is stored under the "message" key.
    """

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
        }
        if isinstance(record.msg, dict):
            data.update(record.msg)
        else:
            data["message"] = record.getMessage()
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger that emits JSON to stderr.

    Idempotent — calling twice with the same name returns the same logger
    without adding duplicate handlers.

    propagate=True (the default) is intentional:
      Records propagate to the root logger so pytest's caplog fixture can
      capture them. caplog installs its handler on root — with propagate=False
      the records would never reach caplog.

    Known production side-effect: if uvicorn or gunicorn has configured the
    root logger with its own StreamHandler, each record may be emitted twice
    (once by our JsonFormatter, once by the root handler). To suppress root
    duplicates in production, remove root logger handlers at startup:
        logging.root.handlers.clear()  # after uvicorn/gunicorn sets them up
    For this learning project the JSON line in app.log is what matters —
    the extra root-format line is harmless.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


# ---------------------------------------------------------------------------
# CloudWatch metric publisher
# ---------------------------------------------------------------------------

_METRIC_NAMESPACE = settings.cloudwatch_namespace


def _publish_metrics(path: str, duration_ms: float, status_code: int) -> None:
    """
    Publish RequestCount, RequestDuration, and (on 5xx) ErrorCount.

    Skipped entirely when CLOUDWATCH_NAMESPACE is empty — keeps local dev
    and tests clean without any mocking.

    Errors are swallowed so a CloudWatch outage never breaks API responses.
    """
    namespace = _METRIC_NAMESPACE or settings.cloudwatch_namespace
    if not namespace:
        return
    try:
        client = boto3.client("cloudwatch", region_name=settings.aws_region)
        dimensions = [{"Name": "Path", "Value": path}]
        metric_data: list[dict[str, Any]] = [
            {
                "MetricName": "RequestCount",
                "Dimensions": dimensions,
                "Value": 1.0,
                "Unit": "Count",
            },
            {
                "MetricName": "RequestDuration",
                "Dimensions": dimensions,
                "Value": duration_ms,
                "Unit": "Milliseconds",
            },
        ]
        if status_code >= 500:
            metric_data.append(
                {
                    "MetricName": "ErrorCount",
                    "Dimensions": dimensions,
                    "Value": 1.0,
                    "Unit": "Count",
                }
            )
        client.put_metric_data(Namespace=namespace, MetricData=metric_data)
    except Exception:
        # Never let a CloudWatch error affect the API response.
        # Log at WARNING level using the module logger.
        _logger.warning({"event": "cloudwatch_metric_error", "path": path})


# ---------------------------------------------------------------------------
# Logging middleware
# ---------------------------------------------------------------------------

_logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Emit one structured JSON log record per HTTP request.

    Fields logged:
        event        — "http_request" (fixed)
        method       — HTTP method (GET, POST, …)
        path         — URL path (/clubs/, /releases/, …)
        status_code  — response HTTP status (200, 201, 401, 403, 500, …)
        duration_ms  — wall-clock time from first byte received to last byte sent
        user_id      — integer ID from the users shadow table, or None for
                       unauthenticated requests and tests that use overrides
        request_id   — UUID from RequestIdMiddleware (empty string if that
                       middleware is not in the stack)

    Middleware execution order in main.py:
        app.add_middleware(LoggingMiddleware)   ← added first → inner
        app.add_middleware(RequestIdMiddleware) ← added second → outer (runs first)

    RequestIdMiddleware sets request_id_var before LoggingMiddleware.dispatch
    receives control, so `request_id_var.get()` always returns the correct ID.

    user_id is read from request.state.user_id, which get_current_user
    sets when a valid JWT is present. For unauthenticated routes or test
    overrides that skip the real get_current_user, the value is None.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.monotonic()
        status_code = 500  # default if an exception propagates out of call_next
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # BaseHTTPMiddleware.call_next re-raises unhandled exceptions from
            # the inner app (even after ExceptionMiddleware has handled them).
            # We still want to log and publish metrics for the 500 before
            # re-raising so ServerErrorMiddleware can return the error response.
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            user_id: int | None = getattr(request.state, "user_id", None)
            _logger.error(
                {
                    "event": "http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "user_id": user_id,
                    "request_id": request_id_var.get(),
                }
            )
            _publish_metrics(request.url.path, duration_ms, 500)
            raise

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        user_id = getattr(request.state, "user_id", None)

        _logger.info(
            {
                "event": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "user_id": user_id,
                "request_id": request_id_var.get(),
            }
        )
        _publish_metrics(request.url.path, duration_ms, status_code)
        return response
