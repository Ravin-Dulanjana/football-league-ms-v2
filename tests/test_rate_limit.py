"""
Tests for the /auth/login rate limiter.

slowapi uses an in-memory counter keyed by client IP (via X-Forwarded-For
or request.client.host).  We use unique X-Forwarded-For headers per test
so other test modules that also hit /auth/login don't bleed into these
counters.

We mock `app.services.cognito.login` to return a 401 HTTPException so the
route produces a proper error response (not a 500) while still counting
against the limit.  On the 6th request from the same IP the rate limiter
fires before reaching Cognito and returns 429.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

_MOCK_401 = HTTPException(status_code=401, detail="Invalid email or password")


def _post_login(client: TestClient, *, ip: str) -> int:
    r = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong"},
        headers={"X-Forwarded-For": ip},
    )
    return int(r.status_code)


class TestLoginRateLimit:
    def test_sixth_request_is_rate_limited(self, client: TestClient) -> None:
        ip = "10.99.1.1"
        with patch("app.services.cognito.login", side_effect=_MOCK_401):
            for i in range(5):
                status = _post_login(client, ip=ip)
                assert status == 401, f"Expected 401 on attempt {i + 1}, got {status}"

            # 6th request — rate limiter fires before Cognito is called
            status = _post_login(client, ip=ip)
        assert status == 429

    def test_different_ip_not_affected(self, client: TestClient) -> None:
        """Exhausting the limit for one IP must not block a different IP."""
        exhausted_ip = "10.99.1.2"
        clean_ip = "10.99.1.3"
        with patch("app.services.cognito.login", side_effect=_MOCK_401):
            # Exhaust the limit for exhausted_ip (6 calls — last one is 429)
            for _ in range(6):
                _post_login(client, ip=exhausted_ip)

            # clean_ip should still have a fresh counter
            status = _post_login(client, ip=clean_ip)
        assert status == 401, f"Expected 401 for clean IP, got {status}"
