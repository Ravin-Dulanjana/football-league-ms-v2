"""
Tests for Phase 6 authentication: JWT verification, role guards, and the login endpoint.

What is tested here:
  - _decode_token: valid token, expired token, tampered signature
  - require_role: 403 when role not in allowed set
  - POST /auth/login: success path and wrong-password path (both with mocked Cognito)
  - Service-layer player guard: player cannot decide another player's registration
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
import pytest
from botocore.exceptions import ClientError
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.dependencies as deps
from app.dependencies import CurrentUser, _decode_token, get_current_user
from app.models.club import Club, ClubStatus
from app.models.player import Player
from app.models.registration import RegistrationRequest, RegistrationRequestStatus
from app.models.season import Season
from main import app

# ---------------------------------------------------------------------------
# Shared constants — fake Cognito configuration used in all JWT tests
# ---------------------------------------------------------------------------

_FAKE_KID = "test-rsa-key-1"
_FAKE_POOL_ID = "ap-southeast-1_TestPool123"
_FAKE_CLIENT_ID = "test-client-id-abc"
_FAKE_REGION = "ap-southeast-1"
_FAKE_ISSUER = f"https://cognito-idp.{_FAKE_REGION}.amazonaws.com/{_FAKE_POOL_ID}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rsa_key_pair() -> tuple[RSAPrivateKey, RSAPublicKey]:
    """Return (private_key, public_key) as a fresh RSA-2048 pair."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    return private_key, private_key.public_key()


def _encode_token(
    private_key: RSAPrivateKey,
    *,
    expired: bool = False,
    wrong_sig: bool = False,
    **extra_claims: Any,
) -> str:
    """
    Build a JWT signed with `private_key`.

    `expired=True`    — sets `exp` 60 s in the past
    `wrong_sig=True`  — tampers the signature byte so verification fails
    """
    now = int(time.time())
    payload = {
        "sub": "cognito-sub-test-001",
        "email": "testuser@example.com",
        "custom:role": "player",
        "iss": _FAKE_ISSUER,
        "aud": _FAKE_CLIENT_ID,
        "iat": now - 10,
        "exp": (now - 60) if expired else (now + 3600),
        **extra_claims,
    }
    token: str = jwt.encode(
        payload, private_key, algorithm="RS256", headers={"kid": _FAKE_KID}
    )
    if wrong_sig:
        # Tamper the FIRST character of the signature.
        # RSA-2048 → 256 bytes → 342 base64url chars.
        # The first char encodes the top 6 bits of byte 0 — all 6 are
        # meaningful (not zero-padding), so flipping it always corrupts
        # the signature.  The last 2 chars have only 2+0 meaningful bits
        # and can silently survive a single-bit flip.
        header_b64, payload_b64, sig_b64 = token.split(".")
        first_char = sig_b64[0]
        new_first = "A" if first_char != "A" else "B"
        token = ".".join([header_b64, payload_b64, new_first + sig_b64[1:]])
    return token


@pytest.fixture()
def jwks_env(monkeypatch: pytest.MonkeyPatch) -> RSAPrivateKey:
    """
    Inject an RSA public key into the JWKS cache and configure fake Cognito settings.

    After the test, monkeypatch restores all values automatically.
    """
    private_key, public_key = _make_rsa_key_pair()

    # Populate the JWKS cache — avoids any real HTTPS call to Cognito
    monkeypatch.setitem(deps._jwks_by_kid, _FAKE_KID, public_key)
    monkeypatch.setattr(deps, "_jwks_fetched_at", time.monotonic())

    # Point settings at the fake pool
    monkeypatch.setattr(deps.settings, "cognito_user_pool_id", _FAKE_POOL_ID)
    monkeypatch.setattr(deps.settings, "cognito_client_id", _FAKE_CLIENT_ID)
    monkeypatch.setattr(deps.settings, "cognito_region", _FAKE_REGION)

    return private_key  # test functions receive the private key to sign tokens


# ---------------------------------------------------------------------------
# JWT unit tests — _decode_token called directly (no FastAPI, no DB)
# ---------------------------------------------------------------------------


def test_decode_valid_token(jwks_env: RSAPrivateKey) -> None:
    """A correctly signed, non-expired token with matching iss/aud is accepted."""
    private_key = jwks_env
    token = _encode_token(private_key)

    claims = _decode_token(token)

    assert claims["sub"] == "cognito-sub-test-001"
    assert claims["email"] == "testuser@example.com"
    assert claims["custom:role"] == "player"


def test_decode_expired_token_raises_401(jwks_env: RSAPrivateKey) -> None:
    """
    An expired token raises HTTPException 401 with a message about expiry.

    Why this matters: after 1 hour, clients must refresh via /auth/refresh.
    Old tokens must not be accepted silently.
    """
    private_key = jwks_env
    token = _encode_token(private_key, expired=True)

    with pytest.raises(HTTPException) as exc_info:
        _decode_token(token)

    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_decode_tampered_signature_raises_401(jwks_env: RSAPrivateKey) -> None:
    """
    A token with a modified signature raises HTTPException 401.

    Why this matters: the whole security model rests on the RSA signature.
    A tampered payload must be rejected before any claims are trusted.
    """
    private_key = jwks_env
    token = _encode_token(private_key, wrong_sig=True)

    with pytest.raises(HTTPException) as exc_info:
        _decode_token(token)

    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# require_role — 403 guard
# ---------------------------------------------------------------------------


def test_require_role_returns_403_for_wrong_role(client: TestClient) -> None:
    """
    A user with role 'player' calling an endpoint restricted to
    super_admin/league_admin gets 403, not 404 or 200.

    This confirms that require_role() reads the role from the overridden
    get_current_user and enforces the guard correctly.
    """
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=1, role="player"
    )
    response = client.post("/clubs/", json={"name": "Unauthorized FC", "code": "UFC"})
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Login endpoint — mocked Cognito
# ---------------------------------------------------------------------------


def test_login_success_returns_all_tokens(client: TestClient) -> None:
    """
    POST /auth/login returns all three tokens when Cognito responds with
    AuthenticationResult. No real AWS call is made.
    """
    fake_auth_result = {
        "AuthenticationResult": {
            "AccessToken": "mock-access-token",
            "IdToken": "mock-id-token",
            "RefreshToken": "mock-refresh-token",
            "ExpiresIn": 3600,
            "TokenType": "Bearer",
        }
    }

    with patch("app.services.cognito.boto3") as mock_boto3:
        mock_idp = MagicMock()
        mock_idp.initiate_auth.return_value = fake_auth_result
        mock_boto3.client.return_value = mock_idp

        response = client.post(
            "/auth/login",
            json={"email": "coach@wattalasc.com", "password": "ValidPass1!"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "mock-access-token"
    assert body["id_token"] == "mock-id-token"
    assert body["refresh_token"] == "mock-refresh-token"
    assert body["expires_in"] == 3600
    assert body["token_type"] == "Bearer"


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    """
    POST /auth/login returns 401 for bad credentials.

    The error message is the same for wrong password AND unknown user —
    this is intentional to prevent user enumeration attacks.
    """

    def raise_not_authorized(**_kwargs: Any) -> None:
        raise ClientError(
            {
                "Error": {
                    "Code": "NotAuthorizedException",
                    "Message": "Incorrect username or password.",
                }
            },
            "InitiateAuth",
        )

    with patch("app.services.cognito.boto3") as mock_boto3:
        mock_idp = MagicMock()
        mock_idp.initiate_auth.side_effect = raise_not_authorized
        mock_boto3.client.return_value = mock_idp

        response = client.post(
            "/auth/login",
            json={"email": "coach@wattalasc.com", "password": "WrongPass99!"},
        )

    assert response.status_code == 401
    # Same message regardless of whether user exists — prevents enumeration
    assert "Invalid email or password" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Player-decides-own-request guard
# ---------------------------------------------------------------------------


def test_player_cannot_decide_another_players_registration(
    client: TestClient,
    db: Session,
) -> None:
    """
    A player can only decide their OWN registration request.

    player_id on the request does not match current_user.player_id → 403.
    This is enforced in the service layer and surfaced as 403 by the router.
    """
    now = datetime.now(tz=UTC)
    club = Club(name="Wattala SC", code="WSC2", status=ClubStatus.ACTIVE)
    player = Player(
        league_player_code="WL-8888",
        full_name="Saman Kumara",
        date_of_birth=datetime(1997, 3, 20).date(),
        nic_number="199703200001",
    )
    season = Season(
        name="2025 Auth Test",
        year=2025,
        registration_open_at=now - timedelta(days=1),
        registration_close_at=now + timedelta(days=30),
    )
    db.add_all([club, player, season])
    db.flush()

    req = RegistrationRequest(
        season_id=season.id,
        club_id=club.id,
        player_id=player.id,
        requested_by_user_id=999,
        status=RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(req)
    db.commit()

    # Act as a different player — player_id intentionally mismatches
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=42, role="player", player_id=player.id + 9999
    )
    response = client.post(
        f"/registration-requests/{req.id}/decide/",
        json={"decision": "accept"},
    )
    assert response.status_code == 403
