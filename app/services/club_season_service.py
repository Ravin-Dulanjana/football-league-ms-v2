"""
ClubSeasonProfile, ClubStaff, and ClubUnlockRequest service.

Business rules:
  ClubSeasonProfile:
    - One per (club_id, season_id) — unique constraint enforced at DB level.
    - Status transitions:
        draft → submitted
        returned/resubmitted → resubmitted   (when re-submitted)
        reviewed → reviewed/approved/returned (league_admin transitions)
    - Submission requires registration window open OR an approved unlock.

  ClubStaff:
    - Max MAX_STAFF_PER_CLUB_SEASON per club per season.
    - Registration window must be open (or active approved unlock).

  ClubUnlockRequest:
    - MIN_APPROVALS = 2 separate league-admin approvals to reach APPROVED.
    - A league_admin cannot approve their own request.
    - Unique constraint on (request_id, approver_id) prevents double-approve.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser
from app.middleware.logging import get_logger
from app.models.club_season import (
    MIN_APPROVALS,
    ClubSeasonComment,
    ClubSeasonProfile,
    ClubSeasonProfileStatus,
    ClubStaff,
    ClubUnlockRequest,
    UnlockApproval,
    UnlockRequestStatus,
)
from app.models.registration import RegistrationRequest, RegistrationRequestStatus
from app.models.season import Season
from app.schemas.club_season import (
    ClubSeasonProfileCreate,
    ClubSeasonProfileTransition,
    ClubStaffCreate,
    CommentCreate,
    UnlockRequestCreate,
)
from app.services import audit_service, notification_service
from app.services.season_service import is_registration_window_open

logger = get_logger(__name__)

MAX_STAFF_PER_CLUB_SEASON = 10
MIN_PLAYERS_PER_CLUB_SEASON = 2  # testing: lower to 2 (prod: 17)

# ---------------------------------------------------------------------------
# ClubSeasonProfile
# ---------------------------------------------------------------------------


def get_profiles(db: Session, current_user: CurrentUser) -> list[ClubSeasonProfile]:
    """Queryset scoped by role."""
    q = select(ClubSeasonProfile)
    if current_user.role == "club_admin":
        q = q.where(ClubSeasonProfile.club_id == current_user.club_id)
    return list(db.execute(q.order_by(ClubSeasonProfile.id.desc())).scalars().all())


def get_profile_by_id(db: Session, profile_id: int) -> ClubSeasonProfile | None:
    return db.get(ClubSeasonProfile, profile_id)


def create_profile(
    db: Session,
    data: ClubSeasonProfileCreate,
    current_user: CurrentUser,
) -> tuple[ClubSeasonProfile | None, str | None]:
    try:
        profile = ClubSeasonProfile(
            club_id=data.club_id,
            season_id=data.season_id,
            status=ClubSeasonProfileStatus.DRAFT,
        )
        db.add(profile)
        db.flush()
        audit_service.write_audit_log(
            db,
            actor_id=current_user.id,
            action="club_season_profile.create",
            entity_type="ClubSeasonProfile",
            entity_id=profile.id,
            details={"club_id": data.club_id, "season_id": data.season_id},
        )
        db.commit()
        db.refresh(profile)
        return profile, None
    except IntegrityError:
        db.rollback()
        return None, "A profile for this club and season already exists."


def submit_profile(
    db: Session,
    profile: ClubSeasonProfile,
    current_user: CurrentUser,
) -> tuple[ClubSeasonProfile | None, str | None]:
    """
    Transition to SUBMITTED (or RESUBMITTED).

    During the registration window: normal submission, no approval needed beyond
    standard league-admin review.

    After the window closes: allowed as a late submission.  is_late is set to
    True and a ClubUnlockRequest is auto-created.  Two league admins from two
    different clubs must approve before the profile is auto-approved.
    """
    season = db.get(Season, profile.season_id)
    if season is None:
        return None, "Season not found."

    allowed_from = {
        ClubSeasonProfileStatus.DRAFT,
        ClubSeasonProfileStatus.RETURNED,
        ClubSeasonProfileStatus.REVIEWED,
    }
    if profile.status not in allowed_from:
        return (
            None,
            f"Cannot submit from status '{profile.status}'. "
            "Profile must be in draft, returned, or reviewed state.",
        )

    accepted_count = db.execute(
        select(func.count()).where(
            RegistrationRequest.club_id == profile.club_id,
            RegistrationRequest.season_id == profile.season_id,
            RegistrationRequest.status == RegistrationRequestStatus.ACCEPTED,
        )
    ).scalar_one()
    if accepted_count < MIN_PLAYERS_PER_CLUB_SEASON:
        return (
            None,
            f"At least {MIN_PLAYERS_PER_CLUB_SEASON} players must be registered "
            f"before submitting. Currently {accepted_count} accepted.",
        )

    window_open = is_registration_window_open(season)
    is_late = not window_open

    now = datetime.now(tz=UTC)
    new_status = (
        ClubSeasonProfileStatus.SUBMITTED
        if profile.status == ClubSeasonProfileStatus.DRAFT
        else ClubSeasonProfileStatus.RESUBMITTED
    )
    profile.status = new_status
    profile.submitted_at = now
    profile.updated_at = now
    profile.is_late = is_late
    db.flush()

    if is_late:
        _ensure_unlock_request(db, profile, current_user)

    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="club_season_profile.submit",
        entity_type="ClubSeasonProfile",
        entity_id=profile.id,
        details={"new_status": new_status.value, "is_late": is_late},
    )

    if is_late:
        notification_service.notify_by_role(
            db,
            role="league_admin",
            event_type="club_profile.late_submitted",
            message=(
                f"Club {profile.club_id} made a LATE squad submission "
                f"(profile id={profile.id}). Requires approval from 2 league "
                "admins from 2 different clubs."
            ),
        )
    else:
        notification_service.notify_by_role(
            db,
            role="league_admin",
            event_type="club_profile.submitted",
            message=(
                f"Club profile (id={profile.id}) for club {profile.club_id} "
                f"has been {new_status.value} and is awaiting review."
            ),
        )
    db.commit()
    db.refresh(profile)
    return profile, None


def transition_profile(
    db: Session,
    profile: ClubSeasonProfile,
    data: ClubSeasonProfileTransition,
    current_user: CurrentUser,
) -> tuple[ClubSeasonProfile | None, str | None]:
    """
    league_admin / super_admin transitions: reviewed, approved, returned.
    """
    target = ClubSeasonProfileStatus(data.target_status)
    valid_from = {
        ClubSeasonProfileStatus.REVIEWED: {
            ClubSeasonProfileStatus.SUBMITTED,
            ClubSeasonProfileStatus.RESUBMITTED,
        },
        ClubSeasonProfileStatus.APPROVED: {ClubSeasonProfileStatus.REVIEWED},
        ClubSeasonProfileStatus.RETURNED: {
            ClubSeasonProfileStatus.SUBMITTED,
            ClubSeasonProfileStatus.RESUBMITTED,
            ClubSeasonProfileStatus.REVIEWED,
        },
    }
    if profile.status not in valid_from.get(target, set()):
        return (
            None,
            f"Cannot transition from '{profile.status}' to '{target.value}'.",
        )

    now = datetime.now(tz=UTC)
    profile.status = target
    profile.updated_at = now
    if target == ClubSeasonProfileStatus.REVIEWED:
        profile.reviewed_at = now
    elif target == ClubSeasonProfileStatus.APPROVED:
        profile.approved_at = now

    # Optional comment on the transition
    if data.comment:
        comment = ClubSeasonComment(
            profile_id=profile.id,
            author_id=current_user.id,
            content=data.comment,
            is_internal=data.is_internal,
        )
        db.add(comment)

    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="club_season_profile.transition",
        entity_type="ClubSeasonProfile",
        entity_id=profile.id,
        details={"from": profile.status.value, "to": target.value},
    )
    # Notify the club_admin(s) for this specific club about the status change
    notification_service.notify_by_role(
        db,
        role="club_admin",
        event_type="club_profile.transitioned",
        message=(
            f"Your club's season profile (id={profile.id}) has been "
            f"moved to '{target.value}'."
        ),
        club_id=profile.club_id,
    )
    db.commit()
    db.refresh(profile)
    return profile, None


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


def get_comments(
    db: Session,
    profile_id: int,
    current_user: CurrentUser,
) -> list[ClubSeasonComment]:
    """
    club_admin sees external comments only (is_internal=False).
    league_admin / super_admin sees all comments.
    """
    q = select(ClubSeasonComment).where(ClubSeasonComment.profile_id == profile_id)
    if current_user.role == "club_admin":
        q = q.where(ClubSeasonComment.is_internal.is_(False))
    return list(db.execute(q.order_by(ClubSeasonComment.created_at)).scalars().all())


def add_comment(
    db: Session,
    profile_id: int,
    data: CommentCreate,
    current_user: CurrentUser,
) -> tuple[ClubSeasonComment | None, str | None]:
    # club_admin cannot post internal comments
    if current_user.role == "club_admin" and data.is_internal:
        return None, "Club admins cannot post internal comments."

    comment = ClubSeasonComment(
        profile_id=profile_id,
        author_id=current_user.id,
        content=data.content,
        is_internal=data.is_internal,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment, None


# ---------------------------------------------------------------------------
# ClubStaff
# ---------------------------------------------------------------------------


def get_staff(
    db: Session,
    current_user: CurrentUser,
    club_id: int | None = None,
    season_id: int | None = None,
) -> list[ClubStaff]:
    """
    Queryset-as-access-control:
      super_admin:    sees all staff
      league_admin:   sees all staff in the system (single-league)
      club_admin:     sees their club's staff only
      other (player): sees only staff where the club profile is submitted/approved
    """
    q = select(ClubStaff)
    if club_id:
        q = q.where(ClubStaff.club_id == club_id)
    if season_id:
        q = q.where(ClubStaff.season_id == season_id)

    if current_user.role == "club_admin":
        q = q.where(ClubStaff.club_id == current_user.club_id)
    elif current_user.role == "player":
        # Players can see staff whose club profile is approved/submitted (public roster)
        approved_statuses = [
            ClubSeasonProfileStatus.SUBMITTED.value,
            ClubSeasonProfileStatus.APPROVED.value,
        ]
        subq = select(ClubSeasonProfile.club_id).where(
            ClubSeasonProfile.status.in_(approved_statuses)
        )
        if season_id:
            subq = subq.where(ClubSeasonProfile.season_id == season_id)
        q = q.where(ClubStaff.club_id.in_(subq))

    return list(db.execute(q.order_by(ClubStaff.id)).scalars().all())


def add_staff(
    db: Session,
    data: ClubStaffCreate,
    current_user: CurrentUser,
) -> tuple[ClubStaff | None, str | None]:
    """
    Add a staff member.  Registration window must be open.
    Max MAX_STAFF_PER_CLUB_SEASON per club per season.
    """
    season = db.get(Season, data.season_id)
    if season is None:
        return None, "Season not found."

    if not is_registration_window_open(season) and not _has_active_unlock(
        db, data.club_id, data.season_id
    ):
        return None, "Registration window is closed for this season."

    # Count existing staff for this club + season
    count = db.execute(
        select(func.count()).where(
            ClubStaff.club_id == data.club_id,
            ClubStaff.season_id == data.season_id,
        )
    ).scalar_one()

    if count >= MAX_STAFF_PER_CLUB_SEASON:
        return (
            None,
            f"Maximum {MAX_STAFF_PER_CLUB_SEASON} staff members allowed "
            "per club per season.",
        )

    staff = ClubStaff(
        club_id=data.club_id,
        season_id=data.season_id,
        full_name=data.full_name,
        role=data.role,
    )
    db.add(staff)
    db.flush()

    # If the club profile is already submitted/approved, alert league admins
    # that a staff change happened after submission.
    submitted_statuses = [
        ClubSeasonProfileStatus.SUBMITTED,
        ClubSeasonProfileStatus.RESUBMITTED,
        ClubSeasonProfileStatus.REVIEWED,
        ClubSeasonProfileStatus.APPROVED,
    ]
    profile_submitted = db.execute(
        select(ClubSeasonProfile).where(
            ClubSeasonProfile.club_id == data.club_id,
            ClubSeasonProfile.season_id == data.season_id,
            ClubSeasonProfile.status.in_(submitted_statuses),
        )
    ).scalar_one_or_none()

    if profile_submitted is not None:
        notification_service.notify_by_role(
            db,
            role="league_admin",
            event_type="club_staff.added_post_submission",
            message=(
                f"Club {data.club_id} added staff member '{data.full_name}' "
                f"after profile submission (profile id={profile_submitted.id})."
            ),
        )

    db.commit()
    db.refresh(staff)
    return staff, None


def remove_staff(
    db: Session,
    staff: ClubStaff,
    current_user: CurrentUser,
) -> tuple[bool, str | None]:
    """Delete a staff record.  Registration window must be open."""
    season = db.get(Season, staff.season_id)
    if season is None:
        return False, "Season not found."

    if not is_registration_window_open(season) and not _has_active_unlock(
        db, staff.club_id, staff.season_id
    ):
        return False, "Registration window is closed."

    # Capture details before deletion for the notification message
    staff_name = staff.full_name
    staff_club_id = staff.club_id
    staff_season_id = staff.season_id

    # Check if the club profile is already submitted/approved before deleting
    submitted_statuses = [
        ClubSeasonProfileStatus.SUBMITTED,
        ClubSeasonProfileStatus.RESUBMITTED,
        ClubSeasonProfileStatus.REVIEWED,
        ClubSeasonProfileStatus.APPROVED,
    ]
    profile_submitted = db.execute(
        select(ClubSeasonProfile).where(
            ClubSeasonProfile.club_id == staff_club_id,
            ClubSeasonProfile.season_id == staff_season_id,
            ClubSeasonProfile.status.in_(submitted_statuses),
        )
    ).scalar_one_or_none()

    db.delete(staff)
    db.flush()

    if profile_submitted is not None:
        notification_service.notify_by_role(
            db,
            role="league_admin",
            event_type="club_staff.removed_post_submission",
            message=(
                f"Club {staff_club_id} removed staff member '{staff_name}' "
                f"after profile submission (profile id={profile_submitted.id})."
            ),
        )

    db.commit()
    return True, None


# ---------------------------------------------------------------------------
# ClubUnlockRequest
# ---------------------------------------------------------------------------


def get_unlock_requests(
    db: Session, current_user: CurrentUser
) -> list[ClubUnlockRequest]:
    """Scoped by role."""
    q = select(ClubUnlockRequest)
    if current_user.role == "club_admin":
        q = q.where(ClubUnlockRequest.club_id == current_user.club_id)
    return list(
        db.execute(q.order_by(ClubUnlockRequest.created_at.desc())).scalars().all()
    )


def get_unlock_request_by_id(db: Session, request_id: int) -> ClubUnlockRequest | None:
    return db.get(ClubUnlockRequest, request_id)


def create_unlock_request(
    db: Session,
    data: UnlockRequestCreate,
    current_user: CurrentUser,
) -> tuple[ClubUnlockRequest | None, str | None]:
    req = ClubUnlockRequest(
        club_id=data.club_id,
        season_id=data.season_id,
        requested_by=current_user.id,
        reason=data.reason,
        status=UnlockRequestStatus.PENDING,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req, None


def decide_unlock_request(
    db: Session,
    req: ClubUnlockRequest,
    decision: str,
    current_user: CurrentUser,
) -> tuple[ClubUnlockRequest | None, str | None]:
    """
    Approve or reject a late-submission unlock request.

    Approval rules:
      - The same person cannot approve twice.
      - Two approvals must come from league admins representing two DIFFERENT
        clubs (tracked via approver_club_id = current_user.club_id).
      - If the approver has no club association, they cannot approve (they
        would not satisfy the "different clubs" requirement).
      - When distinct approving clubs >= MIN_APPROVALS the request becomes
        APPROVED and the linked late profile is auto-approved.

    A rejection by any approver is final.
    """
    if req.requested_by == current_user.id:
        return None, "You cannot approve your own unlock request."

    if req.status != UnlockRequestStatus.PENDING:
        return None, "This request has already been decided."

    now = datetime.now(tz=UTC)

    if decision == "reject":
        req.status = UnlockRequestStatus.REJECTED
        req.decided_at = now
        audit_service.write_audit_log(
            db,
            actor_id=current_user.id,
            action="unlock_request.reject",
            entity_type="ClubUnlockRequest",
            entity_id=req.id,
        )
        db.commit()
        db.refresh(req)
        return req, None

    if decision == "approve":
        approver_club_id = current_user.club_id

        if approver_club_id is None:
            return (
                None,
                "You must be associated with a club to approve late submissions. "
                "Ask a league admin who also holds a club admin role.",
            )

        # Prevent same club from approving twice
        same_club = db.execute(
            select(UnlockApproval).where(
                UnlockApproval.request_id == req.id,
                UnlockApproval.approver_club_id == approver_club_id,
            )
        ).scalar_one_or_none()
        if same_club:
            return None, "Someone from your club has already approved this request."

        # Belt-and-suspenders: prevent the exact same person from approving twice
        existing = db.execute(
            select(UnlockApproval).where(
                UnlockApproval.request_id == req.id,
                UnlockApproval.approver_id == current_user.id,
            )
        ).scalar_one_or_none()
        if existing:
            return None, "You have already approved this request."

        approval = UnlockApproval(
            request_id=req.id,
            approver_id=current_user.id,
            approver_club_id=approver_club_id,
        )
        db.add(approval)
        db.flush()

        # Check distinct approving clubs
        all_approvals = list(
            db.execute(
                select(UnlockApproval).where(UnlockApproval.request_id == req.id)
            )
            .scalars()
            .all()
        )
        distinct_clubs = len(
            {
                a.approver_club_id
                for a in all_approvals
                if a.approver_club_id is not None
            }
        )

        if distinct_clubs >= MIN_APPROVALS:
            req.status = UnlockRequestStatus.APPROVED
            req.decided_at = now
            audit_service.write_audit_log(
                db,
                actor_id=current_user.id,
                action="unlock_request.approve",
                entity_type="ClubUnlockRequest",
                entity_id=req.id,
                details={"distinct_clubs": distinct_clubs},
            )
            _auto_approve_late_profile(db, req, current_user)

        db.commit()
        db.refresh(req)
        return req, None

    return None, f"Unknown decision: {decision}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _has_active_unlock(db: Session, club_id: int, season_id: int) -> bool:
    """True if there is an APPROVED unlock request for this club+season."""
    result = db.execute(
        select(ClubUnlockRequest).where(
            ClubUnlockRequest.club_id == club_id,
            ClubUnlockRequest.season_id == season_id,
            ClubUnlockRequest.status == UnlockRequestStatus.APPROVED,
        )
    ).scalar_one_or_none()
    return result is not None


def _ensure_unlock_request(
    db: Session,
    profile: ClubSeasonProfile,
    current_user: CurrentUser,
) -> ClubUnlockRequest:
    """Get or create a PENDING unlock request for this club+season (idempotent)."""
    existing = db.execute(
        select(ClubUnlockRequest).where(
            ClubUnlockRequest.club_id == profile.club_id,
            ClubUnlockRequest.season_id == profile.season_id,
            ClubUnlockRequest.status == UnlockRequestStatus.PENDING,
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    req = ClubUnlockRequest(
        club_id=profile.club_id,
        season_id=profile.season_id,
        requested_by=current_user.id,
        reason=f"Late squad submission (profile id={profile.id})",
        status=UnlockRequestStatus.PENDING,
    )
    db.add(req)
    db.flush()
    return req


def _auto_approve_late_profile(
    db: Session,
    req: ClubUnlockRequest,
    current_user: CurrentUser,
) -> None:
    """Auto-approve the late ClubSeasonProfile when its unlock request is approved."""
    profile = db.execute(
        select(ClubSeasonProfile).where(
            ClubSeasonProfile.club_id == req.club_id,
            ClubSeasonProfile.season_id == req.season_id,
            ClubSeasonProfile.is_late.is_(True),
            ClubSeasonProfile.status.in_(
                [ClubSeasonProfileStatus.SUBMITTED, ClubSeasonProfileStatus.RESUBMITTED]
            ),
        )
    ).scalar_one_or_none()
    if profile is None:
        return
    now = datetime.now(tz=UTC)
    profile.status = ClubSeasonProfileStatus.APPROVED
    profile.approved_at = now
    profile.updated_at = now
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="club_season_profile.auto_approved_late",
        entity_type="ClubSeasonProfile",
        entity_id=profile.id,
    )
    notification_service.notify_by_role(
        db,
        role="club_admin",
        event_type="club_profile.late_approved",
        message=(
            f"Your club's late squad submission (profile id={profile.id}) "
            "has been approved by 2 club representatives."
        ),
        club_id=req.club_id,
    )
