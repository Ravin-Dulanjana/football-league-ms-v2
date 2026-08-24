"""
Shared rate-limiter instance used across the application.

Centralised here so routers can import the same `limiter` object that
`main.py` registers on `app.state` — slowapi looks up the limiter via
`request.app.state.limiter`, so all decorators must reference the identical
instance.

Key function: `get_remote_address` reads `X-Forwarded-For` first (set by
Nginx/ALB in production), then falls back to `request.client.host`.  Behind
Nginx this gives the real client IP rather than the proxy's IP.

Storage: in-memory (default).  For multi-process deployments (multiple
Gunicorn workers) the counters are per-process, so the effective limit is
`limit × workers`.  Migrate to a shared Redis store if strict per-IP
accounting across workers is required.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter


def _client_ip(request: Request) -> str:
    """
    Return the real client IP for rate-limiting purposes.

    Reads X-Forwarded-For first — set by Nginx in production with:
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    Falls back to the direct connection host (useful in dev and tests).

    Only the first address in X-Forwarded-For is trusted; subsequent hops
    are appended by intermediate proxies and could be spoofed.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=_client_ip)
