"""Pydantic schemas for ClubSeasonProfile, ClubStaff, ClubUnlockRequest."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# ClubSeasonProfile
# ---------------------------------------------------------------------------


class ClubSeasonProfileCreate(BaseModel):
    club_id: int
    season_id: int


class ClubSeasonProfileRead(BaseModel):
    id: int
    club_id: int
    season_id: int
    status: str
    submitted_at: datetime | None
    reviewed_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClubSeasonProfileTransition(BaseModel):
    """
    Body for POST /club-season-profiles/{id}/transition/
    Used by league_admin / super_admin.
    """

    target_status: str
    comment: str | None = None
    is_internal: bool = False

    @field_validator("target_status")
    @classmethod
    def validate_target(cls, v: str) -> str:
        valid = {"reviewed", "approved", "returned"}
        if v not in valid:
            raise ValueError(f"target_status must be one of {valid}")
        return v


# ---------------------------------------------------------------------------
# ClubSeasonComment
# ---------------------------------------------------------------------------


class CommentCreate(BaseModel):
    content: str
    is_internal: bool = False


class CommentRead(BaseModel):
    id: int
    profile_id: int
    author_id: int | None
    content: str
    is_internal: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ClubStaff
# ---------------------------------------------------------------------------


class ClubStaffCreate(BaseModel):
    club_id: int
    season_id: int
    full_name: str
    role: str


class ClubStaffRead(BaseModel):
    id: int
    club_id: int
    season_id: int
    full_name: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ClubUnlockRequest
# ---------------------------------------------------------------------------


class UnlockRequestCreate(BaseModel):
    club_id: int
    season_id: int
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason cannot be blank")
        return v


class UnlockRequestDecide(BaseModel):
    decision: str  # "approve" or "reject"

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        if v not in {"approve", "reject"}:
            raise ValueError("decision must be 'approve' or 'reject'")
        return v


class UnlockRequestRead(BaseModel):
    id: int
    club_id: int
    season_id: int
    reason: str
    status: str
    approval_count: int
    created_at: datetime
    decided_at: datetime | None

    model_config = {"from_attributes": True}
