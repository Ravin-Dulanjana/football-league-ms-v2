"""
Boto3 wrapper for Cognito InitiateAuth, token refresh, and sign-out.

All functions raise HTTPException so callers (routers) can let exceptions
propagate without extra try/except blocks.

Security notes
──────────────
- We never log passwords or full tokens.
- "Invalid credentials" is returned for both wrong password AND unknown user
  to prevent user enumeration (an attacker cannot tell which condition failed).
- The Cognito User Pool Client is created WITHOUT a client secret in the CDK
  stack, so no SECRET_HASH is required here. If a secret is added later,
  compute SECRET_HASH = HMAC_SHA256(username + client_id, client_secret)
  and pass it in AuthParameters.
"""

from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


def _cognito_client() -> Any:
    return boto3.client("cognito-idp", region_name=settings.cognito_region)


def login(email: str, password: str) -> dict[str, Any]:
    """
    Call Cognito USER_PASSWORD_AUTH and return either tokens or a challenge dict.

    Normal success → tokens dict (access_token, id_token, refresh_token, …)
    Challenge      → { challenge: "NEW_PASSWORD_REQUIRED", session, email }

    Raises 401 for bad credentials, 503 if Cognito is unreachable.
    """
    client = _cognito_client()
    try:
        resp = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
            ClientId=settings.cognito_client_id,
        )
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("NotAuthorizedException", "UserNotFoundException"):
            # Return the same message for both — prevents user enumeration
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        if error_code == "UserNotConfirmedException":
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Account email not verified — check your inbox",
            ) from exc
        logger.exception("Unexpected Cognito error during login")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service unavailable"
        ) from exc

    # Admin-created or admin-reset accounts come back as a challenge instead of tokens.
    # Return the challenge info so the router can pass it to the frontend, which will
    # call /auth/complete-challenge once the user enters their new password.
    if resp.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
        return {
            "challenge": "NEW_PASSWORD_REQUIRED",
            "session": resp["Session"],
            "email": email,
        }

    result = resp.get("AuthenticationResult")
    if not result:
        logger.error("Cognito login: no AuthenticationResult and no ChallengeName")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Authentication service returned an unexpected response",
        )

    return {
        "access_token": result["AccessToken"],
        "id_token": result["IdToken"],
        "refresh_token": result["RefreshToken"],
        "expires_in": result["ExpiresIn"],
        "token_type": "Bearer",
    }


def respond_new_password(email: str, new_password: str, session: str) -> dict[str, Any]:
    """
    Complete a NEW_PASSWORD_REQUIRED challenge via RespondToAuthChallenge.

    Called when the user enters their new password after an admin-triggered reset.
    Returns tokens on success.
    """
    client = _cognito_client()
    try:
        resp = client.respond_to_auth_challenge(
            ClientId=settings.cognito_client_id,
            ChallengeName="NEW_PASSWORD_REQUIRED",
            Session=session,
            ChallengeResponses={
                "USERNAME": email,
                "NEW_PASSWORD": new_password,
            },
        )
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("NotAuthorizedException", "ExpiredCodeException"):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Session expired — please sign in again",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        if error_code == "InvalidPasswordException":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Password does not meet the requirements "
                "(min 8 chars, uppercase, lowercase, number, symbol)",
            ) from exc
        logger.exception("Unexpected Cognito error during new-password challenge")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Authentication service returned an unexpected error",
        ) from exc

    result = resp.get("AuthenticationResult")
    if not result:
        logger.error("Cognito challenge complete: no AuthenticationResult returned")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Challenge completed but no tokens returned",
        )

    return {
        "access_token": result["AccessToken"],
        "id_token": result["IdToken"],
        "refresh_token": result.get("RefreshToken"),
        "expires_in": result["ExpiresIn"],
        "token_type": "Bearer",
    }


def refresh(refresh_token: str) -> dict[str, Any]:
    """
    Exchange a refresh token for new access and ID tokens.

    Raises 401 if the refresh token is expired or revoked (e.g. after logout).
    """
    client = _cognito_client()
    try:
        resp = client.initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": refresh_token},
            ClientId=settings.cognito_client_id,
        )
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("NotAuthorizedException", "ExpiredCodeException"):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Refresh token expired or revoked — please log in again",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        logger.exception("Unexpected Cognito error during token refresh")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service unavailable"
        ) from exc

    result = resp["AuthenticationResult"]
    return {
        "access_token": result["AccessToken"],
        "id_token": result["IdToken"],
        # Cognito does not reissue the refresh token on refresh
        "expires_in": result["ExpiresIn"],
        "token_type": "Bearer",
    }


def logout(access_token: str) -> None:
    """
    Invalidate all tokens for the user via GlobalSignOut.

    After this call:
    - The refresh token is immediately revoked (cannot get new tokens).
    - The current access/ID tokens remain valid until they expire (up to 1h).
      This is a fundamental limitation of stateless JWTs — see module docstring.
    """
    client = _cognito_client()
    try:
        client.global_sign_out(AccessToken=access_token)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code == "NotAuthorizedException":
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid or already-expired access token",
            ) from exc
        logger.exception("Unexpected Cognito error during logout")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service unavailable"
        ) from exc
