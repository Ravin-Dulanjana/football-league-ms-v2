"""
Authentication endpoints — login, token refresh, logout, and challenge completion.

POST /auth/login              — exchange email+password for tokens (or a challenge)
POST /auth/complete-challenge — complete NEW_PASSWORD_REQUIRED challenge
POST /auth/refresh            — exchange refresh token for new access+ID tokens
POST /auth/logout             — revoke refresh token via GlobalSignOut
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import jwt as pyjwt
from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.rate_limit import limiter
from app.services import cognito

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CompleteChallengeRequest(BaseModel):
    email: EmailStr
    new_password: str
    session: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    id_token: str
    refresh_token: str | None = None
    expires_in: int
    token_type: str = "Bearer"


# Login has no response_model — it returns either TokenResponse fields OR
# { challenge, session, email } for a NEW_PASSWORD_REQUIRED challenge.
@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, data: LoginRequest) -> dict[str, Any]:
    """
    Authenticate with email and password.

    Rate-limited to 5 attempts per minute per client IP to slow brute-force.
    Behind Nginx, X-Forwarded-For carries the real client IP.

    Normal response: Cognito tokens (use id_token as Bearer on subsequent calls).
    Challenge response: { challenge: "NEW_PASSWORD_REQUIRED", session, email }
      — returned when the account requires a password change (admin reset or
        first login after account creation). The client should call
        POST /auth/complete-challenge with the new password and session.
    """
    return cognito.login(data.email, data.password)


@router.post("/complete-challenge", response_model=TokenResponse)
def complete_challenge(
    data: CompleteChallengeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Complete a NEW_PASSWORD_REQUIRED Cognito challenge.

    Call this after /auth/login returns { challenge: "NEW_PASSWORD_REQUIRED" }.
    On success returns full tokens and clears the force_password_change flag.
    """
    tokens = cognito.respond_new_password(data.email, data.new_password, data.session)

    # Clear the app-level flag so the user is not prompted again
    user = db.execute(select(User).where(User.email == data.email)).scalar_one_or_none()
    if user and user.force_password_change:
        user.force_password_change = False
        db.commit()

    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(data: RefreshRequest) -> dict[str, Any]:
    """
    Exchange a refresh token for new access and ID tokens.

    Cognito does not reissue a new refresh token on refresh — use the same
    refresh token until it expires (30 days) or until the user logs out.
    """
    return cognito.refresh(data.refresh_token)


@router.post("/logout", status_code=204)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> None:
    """
    Revoke all tokens for the authenticated user via Cognito GlobalSignOut.

    Requires the ACCESS token (not the ID token) in the Authorization header.

    After calling GlobalSignOut the refresh token is immediately revoked.
    The ID/access tokens would normally remain valid until their `exp` (up to
    1 hour), but we close this gap by stamping `last_logout_at` on the User
    row.  get_current_user rejects any token whose `iat` is before that
    timestamp, so the user is effectively logged out immediately.
    """
    access_token = credentials.credentials
    cognito.logout(access_token)

    # Decode the access token (no signature verification — GlobalSignOut already
    # validated it server-side) to extract the Cognito sub and find the User row.
    try:
        claims = pyjwt.decode(access_token, options={"verify_signature": False})
        cognito_sub: str = claims.get("sub", "")
    except Exception:
        cognito_sub = ""

    if cognito_sub:
        user = db.execute(
            select(User).where(User.cognito_sub == cognito_sub)
        ).scalar_one_or_none()
        if user is not None:
            user.last_logout_at = datetime.now(tz=UTC)
            db.commit()
