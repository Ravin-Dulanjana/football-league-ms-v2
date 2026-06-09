"""
Request ID middleware.

Assigns a unique UUID to every incoming request and makes it available
throughout the entire request-response lifecycle via a ContextVar.

Why ContextVar (not a thread-local or global):
    FastAPI uses asyncio — multiple requests run concurrently in the same
    OS thread. thread-locals are shared across concurrent coroutines (they
    only see one "thread"). ContextVar gives each asyncio Task its own
    isolated slot, so concurrent requests never see each other's IDs.

Usage (anywhere in the call stack for this request):
    from app.middleware.request_id import request_id_var
    rid = request_id_var.get()   # "" if not inside a request context
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Holds the request ID for the current request.
# Default is "" so code outside a request context always gets a safe value.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Assigns a unique UUID to every request.

    Priority:
      1. Uses the value of the X-Request-ID header if the client provided one.
         This allows distributed tracing — a client or upstream gateway can
         set the ID and correlate logs across services.
      2. Falls back to a freshly generated UUID4 otherwise.

    The ID is:
      - Stored in `request_id_var` (ContextVar) so service code can read it
        without passing it as a function argument.
      - Added to the response as the X-Request-ID header so clients can
        correlate their request with server-side log entries.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Set the ContextVar for this request's async context chain.
        # Reset it when the request is done to avoid leaking IDs across
        # requests if the same task is somehow reused.
        token = request_id_var.set(req_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = req_id
        return response
