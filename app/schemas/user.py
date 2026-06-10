"""Pydantic schemas for user management endpoints."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, field_validator, model_validator


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

    When role=player, pass full_name, date_of_birth, and nic_number.
    The backend creates the Player record automatically — do not pass player_id.

    When role=club_admin, club_id is required.
    """

    email: str
    role: str
    club_id: int | None = None
    # Temporary password — must be changed on first login.
    # Must meet Cognito's password policy (min 8, upper, lower, digit, symbol).
    temporary_password: str

    # Player profile fields — required when role=player, ignored otherwise.
    full_name: str | None = None
    date_of_birth: date | None = None
    nic_number: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = {"super_admin", "league_admin", "club_admin", "player"}
        if v not in valid:
            raise ValueError(f"role must be one of {valid}")
        return v

    @model_validator(mode="after")
    def player_fields_required(self) -> UserCreate:
        if self.role == "player":
            missing = [
                f
                for f in ("full_name", "date_of_birth", "nic_number")
                if not getattr(self, f)
            ]
            if missing:
                raise ValueError(
                    f"full_name, date_of_birth, and nic_number are required "
                    f"when role=player (missing: {', '.join(missing)})"
                )
        return self


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
