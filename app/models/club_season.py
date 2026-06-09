"""
ClubSeasonProfile — a club's submission for a given season.

Lifecycle:
  draft → submitted → reviewed → approved
                   ↘              ↗
                    returned → resubmitted → reviewed → approved

One profile per (club_id, season_id) — enforced by unique constraint.

ClubSeasonComment — comments on a profile from league admins or club admins.
  is_internal=True: only league_admin / super_admin can see these.
  is_internal=False: club_admin can also see these.

ClubStaff — non-player club staff registered for a season (max 6 per club).

ClubUnlockRequest — a club's request to re-open the registration window
  after it has closed.  Requires MIN_APPROVALS=2 separate league-admin
  approvals before it becomes APPROVED.

UnlockApproval — tracks each individual approval to enforce the 2-approval
  rule and prevent self-approval.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# ---------------------------------------------------------------------------
# ClubSeasonProfile
# ---------------------------------------------------------------------------

MIN_APPROVALS = 2  # number of separate league-admin approvals needed for unlock


class ClubSeasonProfileStatus(enum.StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    RETURNED = "returned"
    RESUBMITTED = "resubmitted"


class ClubSeasonProfile(Base):
    __tablename__ = "club_season_profiles"
    __table_args__ = (
        UniqueConstraint("club_id", "season_id", name="uq_club_season_profile"),
        Index("ix_csp_season_status", "season_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ClubSeasonProfileStatus] = mapped_column(
        Enum(
            ClubSeasonProfileStatus,
            name="clubseasonprofilestatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ClubSeasonProfileStatus.DRAFT,
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    comments: Mapped[list[ClubSeasonComment]] = relationship(
        "ClubSeasonComment", back_populates="profile", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# ClubSeasonComment
# ---------------------------------------------------------------------------


class ClubSeasonComment(Base):
    __tablename__ = "club_season_comments"
    __table_args__ = (Index("ix_csc_profile_internal", "profile_id", "is_internal"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("club_season_profiles.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Internal comments are only visible to league_admin / super_admin.
    # External comments are visible to club_admin too.
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    profile: Mapped[ClubSeasonProfile] = relationship(
        "ClubSeasonProfile", back_populates="comments"
    )


# ---------------------------------------------------------------------------
# ClubStaff
# ---------------------------------------------------------------------------


class ClubStaff(Base):
    __tablename__ = "club_staff"
    __table_args__ = (Index("ix_club_staff_club_season", "club_id", "season_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # e.g. "coach", "physio", "manager", "kit_man", etc.
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# ClubUnlockRequest + UnlockApproval
# ---------------------------------------------------------------------------


class UnlockRequestStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ClubUnlockRequest(Base):
    """
    A club's request to reopen the registration window after it has closed.

    Requires MIN_APPROVALS (2) separate league-admin approvals.  Tracked via
    the UnlockApproval join table.  A league_admin cannot approve their own
    request (enforced in the service layer).
    """

    __tablename__ = "club_unlock_requests"
    __table_args__ = (Index("ix_unlock_requests_club_season", "club_id", "season_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    requested_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[UnlockRequestStatus] = mapped_column(
        Enum(
            UnlockRequestStatus,
            name="unlockrequeststatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UnlockRequestStatus.PENDING,
        nullable=False,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    approvals: Mapped[list[UnlockApproval]] = relationship(
        "UnlockApproval", back_populates="request", cascade="all, delete-orphan"
    )


class UnlockApproval(Base):
    """
    One approval record per league-admin per unlock request.

    The unique constraint on (request_id, approver_id) prevents the same
    league_admin from approving twice.
    """

    __tablename__ = "unlock_approvals"
    __table_args__ = (
        UniqueConstraint(
            "request_id", "approver_id", name="uq_unlock_approval_request_approver"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("club_unlock_requests.id", ondelete="CASCADE"), nullable=False
    )
    approver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    request: Mapped[ClubUnlockRequest] = relationship(
        "ClubUnlockRequest", back_populates="approvals"
    )
