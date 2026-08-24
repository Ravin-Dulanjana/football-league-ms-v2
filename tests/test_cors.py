"""
Tests for CORS middleware behaviour.

`settings.allowed_origins` defaults to "http://localhost:3000" in the test
environment, so we test against that value.  We don't need to patch or
re-instantiate the middleware — the default already gives us one allowed and
one blocked origin to exercise both code paths.

We verify three things:
1. OPTIONS preflight from the allowed origin → 200 + ACAO header present.
2. OPTIONS preflight from a non-allowed origin → 400 + ACAO header absent.
3. Simple GET from the allowed origin → ACAO header echoed in the response.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

ALLOWED = "http://localhost:3000"
BLOCKED = "https://evil.example.com"
# Any route that accepts GET — /seasons/ is registered and returns a list.
_GET_PATH = "/seasons/"


class TestCorsPreflight:
    def test_allowed_origin_preflight(self, client: TestClient) -> None:
        response = client.options(
            _GET_PATH,
            headers={
                "Origin": ALLOWED,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == ALLOWED

    def test_blocked_origin_preflight_has_no_acao(self, client: TestClient) -> None:
        response = client.options(
            _GET_PATH,
            headers={
                "Origin": BLOCKED,
                "Access-Control-Request-Method": "GET",
            },
        )
        # Starlette CORSMiddleware returns 400 for preflights from disallowed origins.
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers

    def test_allowed_origin_simple_get_echoes_acao(self, client: TestClient) -> None:
        response = client.get(
            _GET_PATH,
            headers={"Origin": ALLOWED},
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == ALLOWED
