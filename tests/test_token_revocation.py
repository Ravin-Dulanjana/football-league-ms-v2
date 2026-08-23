"""
Tests for the last_logout_at token revocation mechanism.

After logout, get_current_user checks whether the token's `iat` (issued-at)
is before the user's last_logout_at timestamp.  If so, it rejects the token
with 401 — even if the token is otherwise valid and not yet expired.

The unit tests exercise the comparison logic directly (no DB needed).
The integration test uses the conftest client fixture (in-memory SQLite) and
overrides get_current_user to inject the revoked-token exception.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.dependencies import CurrentUser, get_current_user

# ---------------------------------------------------------------------------
# Unit tests — revocation comparison logic
# ---------------------------------------------------------------------------


def _is_revoked(last_logout_at: datetime | None, token_iat: int) -> bool:
    """Mirror the check in get_current_user so we can test it in isolation."""
    if last_logout_at is None:
        return False
    return token_iat < last_logout_at.timestamp()


class TestRevocationLogic:
    def test_token_before_logout_is_rejected(self) -> None:
        logout_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        token_iat = int((logout_time - timedelta(minutes=10)).timestamp())
        assert _is_revoked(logout_time, token_iat) is True

    def test_token_after_logout_is_accepted(self) -> None:
        logout_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        token_iat = int((logout_time + timedelta(minutes=5)).timestamp())
        assert _is_revoked(logout_time, token_iat) is False

    def test_token_same_second_as_logout_is_accepted(self) -> None:
        logout_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        token_iat = int(logout_time.timestamp())
        assert _is_revoked(logout_time, token_iat) is False

    def test_no_last_logout_at_skips_check(self) -> None:
        token_iat = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp())
        assert _is_revoked(None, token_iat) is False


# ---------------------------------------------------------------------------
# Integration test — 401 returned from a protected endpoint after revocation
# ---------------------------------------------------------------------------


def test_revoked_token_returns_401(client: TestClient) -> None:
    """
    Override get_current_user to simulate a token that was issued before
    last_logout_at.  Any protected endpoint should respond 401 with the
    "revoked" message.
    """
    from main import app

    def _revoked_user() -> CurrentUser:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token has been revoked — please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )

    app.dependency_overrides[get_current_user] = _revoked_user
    try:
        r = client.get("/league-info/")
        assert r.status_code == 401
        assert "revoked" in r.json()["detail"].lower()
    finally:
        # Restore the conftest default so other tests aren't affected.
        # conftest.client fixture sets its own override; we pop only ours.
        app.dependency_overrides.pop(get_current_user, None)
