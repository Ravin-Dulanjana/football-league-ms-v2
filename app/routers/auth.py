"""
Authentication endpoints — login, token refresh, logout, and challenge completion.

POST /auth/login              — exchange email+password for tokens (or a challenge)
POST /auth/complete-challenge — complete NEW_PASSWORD_REQUIRED challenge
POST /auth/refresh            — exchange refresh token for new access+ID tokens
POST /auth/logout             — revoke refresh token via GlobalSignOut
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
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
def login(data: LoginRequest) -> dict[str, Any]:
    """
    Authenticate with email and password.

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
) -> None:
    """
    Revoke all tokens for the authenticated user via Cognito GlobalSignOut.

    Requires the ACCESS token (not the ID token) in the Authorization header.

    ⚠️  Revocation gap: the ID token and access token remain valid until their
    `exp` claim (up to 1 hour). The refresh token is revoked immediately so
    the user cannot get new tokens, but existing tokens are still accepted by
    any service that validates them independently (including this API).
    """
    cognito.logout(credentials.credentials)
