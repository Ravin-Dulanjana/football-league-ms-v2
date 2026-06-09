"""Pydantic schemas for user management endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class UserRead(BaseModel):
    id: int
    email: str
    role: str
    club_id: int | None
    player_id: int | None
    is_active: bool
    is_deleted: bool
    force_password_change: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    """
    Used by super_admin and league_admin to create user accounts.
    league_admin may only create club_admin accounts.
    """

    email: str
    role: str
    club_id: int | None = None
    player_id: int | None = None
    # Temporary password — must be changed on first login.
    # Must meet Cognito's password policy (min 8, upper, lower, digit, symbol).
    temporary_password: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = {"super_admin", "league_admin", "club_admin", "player"}
        if v not in valid:
            raise ValueError(f"role must be one of {valid}")
        return v


class AccountActionRequest(BaseModel):
    """
    Body for POST /users/{id}/account-action/.

    action values:
      activate        — set is_active=True
      deactivate      — set is_active=False (cannot deactivate own account)
      soft_delete     — super_admin only; sets is_deleted=True, is_active=False
      reset_password  — generate temp password, set force_password_change=True
      update_mobile   — validate new number unique, audit log change
    """

    action: str
    reason: str
    # Required for reset_password; optional for other actions.
    new_value: str | None = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        valid = {
            "activate",
            "deactivate",
            "soft_delete",
            "reset_password",
            "update_mobile",
        }
        if v not in valid:
            raise ValueError(f"action must be one of {valid}")
        return v

    @field_validator("reason")
    @classmethod
    def reason_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason is required and cannot be blank")
        return v


class SoftDeleteRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason is required")
        return v
