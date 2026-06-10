"""
FastAPI dependencies for authentication and role-based access control.

Authentication flow
───────────────────
1. Client sends `Authorization: Bearer <id_token>` on every request.
2. `get_current_user` decodes and verifies the Cognito ID token:
   a. Reads the `kid` from the JWT header.
   b. Fetches the matching RSA public key from Cognito's JWKS URL
      (result is cached for one hour — not fetched on every request).
   c. Verifies signature, expiry, issuer, and audience.
   d. Extracts role, email, and linked DB IDs from custom claims.
3. `user_sync.get_or_create_user` creates/updates a User shadow record
   in PostgreSQL so we have an integer FK-friendly user ID.
4. Returns `CurrentUser` — available in route handlers via `Depends(get_current_user)`.

Role guards
───────────
`require_role(*roles)` is a dependency factory:
  `Depends(require_role("super_admin", "league_admin"))`
raises 403 if the caller's role is not in the allowed set.

JWKS caching
────────────
Keys are cached in `_jwks_by_kid` for `_JWKS_TTL_S` seconds.
On expiry (or if a new `kid` arrives after key rotation), the cache is
refreshed with a single HTTPS call to Cognito. No lock is needed because
all workers share the same cache dict and dict assignment is atomic in CPython.

⚠️  Known limitations
- JWT revocation gap: after `GlobalSignOut`, the ID token stays valid
  until its `exp` (up to 1 hour). The refresh token is revoked immediately,
  so the user can't get new tokens, but the current one still works.
- User sync cost: one indexed DB query per authenticated request. For
  high-throughput production systems, cache `cognito_sub → CurrentUser`
  in Redis instead.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CurrentUser — returned by get_current_user and passed to route handlers.
# Fields are optional with defaults to preserve backward compatibility with
# test code that creates CurrentUser(...) with only a subset of fields.
# ---------------------------------------------------------------------------


class CurrentUser:
    """
    Thin data class holding the authenticated caller's identity.

    Not a Pydantic model — we don't need validation here (the JWT verifier
    already validated the data) and we want to avoid Pydantic's strict
    instantiation in tests that only supply a subset of fields.
    """

    __slots__ = ("id", "cognito_sub", "email", "role", "club_id", "player_id")

    def __init__(
        self,
        id: int,  # noqa: A002
        role: str,
        email: str = "",
        cognito_sub: str = "",
        club_id: int | None = None,
        player_id: int | None = None,
    ) -> None:
        self.id = id
        self.role = role
        self.email = email
        self.cognito_sub = cognito_sub
        self.club_id = club_id
        self.player_id = player_id


# ---------------------------------------------------------------------------
# JWKS — public key cache
# ---------------------------------------------------------------------------

_jwks_by_kid: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL_S: float = 3600.0  # refresh once per hour


def _refresh_jwks() -> None:
    """
    Fetch Cognito's JWKS and populate _jwks_by_kid.

    Called on first use and when the TTL expires. Cognito publishes two
    RSA public keys (one for ID tokens, one for access tokens). We build
    a kid → RSAPublicKey map so verification is a pure in-memory operation.
    """
    global _jwks_fetched_at  # noqa: PLW0603
    if not settings.cognito_jwks_url:
        logger.debug("COGNITO_JWKS_URL not configured — JWKS fetch skipped")
        return
    try:
        # Lazy import — avoids top-level collision between PyJWT and python-jwt.
        # RSAAlgorithm is only needed here; tests never reach this path because
        # they override get_current_user via dependency_overrides.
        from jwt.algorithms import RSAAlgorithm  # noqa: PLC0415

        response = httpx.get(settings.cognito_jwks_url, timeout=5.0)
        response.raise_for_status()
        _jwks_by_kid.clear()
        for key_data in response.json().get("keys", []):
            kid = key_data["kid"]
            _jwks_by_kid[kid] = RSAAlgorithm.from_jwk(json.dumps(key_data))
        _jwks_fetched_at = time.monotonic()
        logger.info("JWKS refreshed — %d keys loaded", len(_jwks_by_kid))
    except Exception:
        logger.exception("Failed to refresh JWKS from %s", settings.cognito_jwks_url)
        raise


def _get_public_key(kid: str) -> Any:
    """
    Return the cached RSA public key for the given `kid`.

    Refreshes the cache if it is empty, stale, or missing the requested kid
    (key rotation case). Raises 401 if the kid is unknown after refresh.
    """
    now = time.monotonic()
    if not _jwks_by_kid or now - _jwks_fetched_at > _JWKS_TTL_S:
        _refresh_jwks()
    if kid not in _jwks_by_kid:
        # Kid unknown — could be after key rotation. Force one refresh.
        _refresh_jwks()
    key = _jwks_by_kid.get(kid)
    if key is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Unknown signing key — token may be from a different User Pool",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return key


# ---------------------------------------------------------------------------
# JWT verification
# ---------------------------------------------------------------------------

_security = HTTPBearer(auto_error=False)


def _decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a Cognito ID token.

    Raises HTTPException 401 on any verification failure so the caller
    never receives a partially-verified token.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.exceptions.DecodeError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Malformed token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    kid = header.get("kid", "")
    public_key = _get_public_key(kid)

    issuer = (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com"
        f"/{settings.cognito_user_pool_id}"
    )

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=issuer,
            options={"require": ["sub", "exp", "iss", "aud"]},
        )
    except jwt.exceptions.ExpiredSignatureError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token has expired — please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.exceptions.InvalidAudienceError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token audience mismatch",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.exceptions.InvalidIssuerError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token issuer mismatch",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.exceptions.PyJWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return claims


# ---------------------------------------------------------------------------
# Main dependency
# ---------------------------------------------------------------------------


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """
    FastAPI dependency — resolve the authenticated caller from their Bearer token.

    Usage in a route:
        current_user: CurrentUser = Depends(get_current_user)

    In tests, override this via:
        app.dependency_overrides[get_current_user] = (
            lambda: CurrentUser(id=1, role="super_admin")
        )

    Phase 7: sets request.state.user_id so LoggingMiddleware can include the
    authenticated user's ID in the structured request log without having to
    re-decode the token a second time.
    """
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = _decode_token(credentials.credentials)

    # Lazy import to avoid circular imports (user_sync imports from app.models)
    from app.services import user_sync  # noqa: PLC0415

    user = user_sync.get_or_create_user(db, claims)
    # Store on request.state so LoggingMiddleware can read it without
    # re-parsing the token. getattr(request.state, "user_id", None) is
    # safe for overridden dependencies in tests that don't set this.
    request.state.user_id = user.id
    return user


# ---------------------------------------------------------------------------
# Role guard factory
# ---------------------------------------------------------------------------


def require_role(*roles: str) -> Callable[..., CurrentUser]:
    """
    Dependency factory — enforce role-based access control.

    Usage:
        current_user: CurrentUser = Depends(require_role("super_admin", "league_admin"))

    Returns the CurrentUser unchanged (so the route handler can still use it).
    Raises 403 if the caller's role is not in the allowed set.
    """

    def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Access denied. This endpoint requires one of: {', '.join(roles)}.",
            )
        return current_user

    return dependency
