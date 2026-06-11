"""Pydantic schemas for user management endpoints."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, field_validator, model_validator

# Valid role values — kept in one place so schemas and tests both import from here.
VALID_ROLES = {"super_admin", "league_admin", "club_admin", "player", "club_staff"}
VALID_MEMBER_TYPES = {"player", "club_staff", "user"}

# Roles that carry governance meaning (shown as extra tags in the UI)
GOVERNANCE_ROLES = frozenset({"super_admin", "league_admin", "club_admin"})

# Role hierarchy for computing the "highest" role to store in users.role
_ROLE_RANK: dict[str, int] = {
    "super_admin": 50,
    "league_admin": 40,
    "club_admin": 30,
    "club_staff": 20,
    "player": 10,
}


def highest_role(roles: list[str]) -> str:
    """Return the single highest-ranked role from a list."""
    if not roles:
        return "player"
    return max(roles, key=lambda r: _ROLE_RANK.get(r, 0))


class GovernanceRoleRead(BaseModel):
    """One entry in a user's governance-role list."""

    role: str
    club_id: int | None
    assigned_at: datetime

    model_config = {"from_attributes": True}


class UserRead(BaseModel):
    id: int
    email: str
    role: str
    member_type: str | None
    club_id: int | None
    player_id: int | None
    is_active: bool
    is_deleted: bool
    force_password_change: bool
    created_at: datetime
    last_login_at: datetime | None
    # All active governance roles (club_admin + league_admin can coexist, etc.)
    governance_roles: list[GovernanceRoleRead] = []

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    """
    Used by super_admin and league_admin to create user accounts.

    Role values:
      player      — creates a Player profile automatically (full_name, dob, nic req'd)
      club_staff  — club member without a player profile; club_id required
      club_admin  — governance role for a club; club_id required; member_type optional
      league_admin — governance role; club_id optional; member_type optional
      super_admin — reserved for the system owner; super_admin only

    member_type tracks the user's base club-membership identity independently of
    their governance role:
      "player"     — has a footballer profile
      "club_staff" — club staff (coach, physio, secretary, etc.)
      None         — pure governance / no club membership (league_admin-only accounts)
    """

    email: str
    role: str
    member_type: str | None = None
    club_id: int | None = None
    temporary_password: str

    # Player profile fields — required when role=player or member_type=player.
    full_name: str | None = None
    date_of_birth: date | None = None
    nic_number: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        return v

    @field_validator("member_type")
    @classmethod
    def validate_member_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_MEMBER_TYPES:
            raise ValueError(f"member_type must be one of {sorted(VALID_MEMBER_TYPES)}")
        return v

    @model_validator(mode="after")
    def validate_fields(self) -> UserCreate:
        # Player profile required for player role or player member_type
        needs_player_profile = self.role == "player" or self.member_type == "player"
        if needs_player_profile:
            missing = [
                f
                for f in ("full_name", "date_of_birth", "nic_number")
                if not getattr(self, f)
            ]
            if missing:
                raise ValueError(
                    "full_name, date_of_birth, and nic_number are required "
                    "when role=player or member_type=player "
                    f"(missing: {', '.join(missing)})"
                )
        # club_id required for club_admin (for club_staff it may be injected
        # server-side when the creator is a club_admin)
        if self.role == "club_admin" and not self.club_id:
            raise ValueError("club_id is required when role=club_admin")
        return self


class AssignRoleRequest(BaseModel):
    """
    Body for PATCH /users/{id}/role/ — change a user's governance role.

    Used during AGMs or when people change positions in the league/club.
    The user's member_type (player/club_staff) is NOT changed by this action.

    new_role    — the role to assign (cannot set super_admin)
    club_id     — required when new_role=club_admin; clears when omitted
    reason      — mandatory audit note (e.g. "Elected club president at AGM 2026")
    """

    new_role: str
    club_id: int | None = None
    reason: str

    @field_validator("new_role")
    @classmethod
    def validate_new_role(cls, v: str) -> str:
        assignable = {"league_admin", "club_admin", "player", "club_staff"}
        if v not in assignable:
            raise ValueError(
                f"new_role must be one of {sorted(assignable)} "
                "(super_admin cannot be assigned via this endpoint)"
            )
        return v

    @field_validator("reason")
    @classmethod
    def reason_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason is required and cannot be blank")
        return v

    @model_validator(mode="after")
    def club_id_for_club_admin(self) -> AssignRoleRequest:
        if self.new_role == "club_admin" and not self.club_id:
            raise ValueError("club_id is required when assigning the club_admin role")
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
    # Required for some actions (e.g. update_mobile uses new_value as the number).
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
