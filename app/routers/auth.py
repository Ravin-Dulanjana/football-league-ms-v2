"""
Authentication endpoints — login, token refresh, and logout.

These endpoints call Cognito directly using boto3. No database writes happen
here — the DB sync occurs on the first subsequent authenticated request.

POST /auth/login    — exchange email+password for Cognito tokens
POST /auth/refresh  — exchange refresh token for new access+ID tokens
POST /auth/logout   — revoke refresh token via GlobalSignOut
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from app.services import cognito

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    id_token: str
    refresh_token: str | None = None
    expires_in: int
    token_type: str = "Bearer"


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest) -> dict:
    """
    Authenticate with email and password.

    Returns Cognito tokens. Use `id_token` in the `Authorization: Bearer` header
    on all subsequent API calls.

    - access_token: short-lived (1h); for calling other AWS services
    - id_token:     short-lived (1h); verify this in FastAPI (contains custom:role)
    - refresh_token: long-lived (30d); send to /auth/refresh to get new tokens
    """
    return cognito.login(data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(data: RefreshRequest) -> dict:
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
