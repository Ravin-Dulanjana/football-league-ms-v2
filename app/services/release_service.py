from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser
from app.middleware.logging import get_logger
from app.middleware.request_id import request_id_var
from app.models.registration import (
    PlayerSeasonRegistration,
    PlayerSeasonRegistrationStatus,
)
from app.models.release import PlayerRelease, ReleaseDocument, ReleaseStatus
from app.schemas.release import ReleaseCreate
from app.services import audit_service
from app.services.events import publish_event

logger = get_logger(__name__)


def get_all_releases(
    db: Session,
    current_user: CurrentUser | None = None,
) -> list[PlayerRelease]:
    """
    Return releases scoped by caller role:
      club_admin  — only releases from their club (from_club_id)
      player      — only releases for their own player_id
      all others  — everything
    """
    q = select(PlayerRelease).order_by(PlayerRelease.id.desc())
    if current_user is not None:
        if current_user.role == "club_admin" and current_user.club_id:
            q = q.where(PlayerRelease.from_club_id == current_user.club_id)
        elif current_user.role == "player" and current_user.player_id:
            q = q.where(PlayerRelease.player_id == current_user.player_id)
    return list(db.execute(q).scalars().all())


def get_release_by_id(db: Session, release_id: int) -> PlayerRelease | None:
    return db.get(PlayerRelease, release_id)


def create_release(
    db: Session,
    data: ReleaseCreate,
    current_user: CurrentUser,
) -> tuple[PlayerRelease | None, str | None]:
    """
    Guards:
      - registration must be ACTIVE
      - no existing release for this registration
    Atomically creates PlayerRelease + ReleaseDocument.
    """
    logger.info(
        {
            "event": "create_release.start",
            "registration_id": data.registration_id,
            "request_id": request_id_var.get(),
        }
    )
    registration = db.get(PlayerSeasonRegistration, data.registration_id)
    if registration is None:
        return None, "Registration not found."
    if registration.status != PlayerSeasonRegistrationStatus.ACTIVE:
        return None, "Only active registrations can be released."

    # Guard: squad list must have been submitted before a release is possible
    from app.models.club_season import (  # noqa: PLC0415
        ClubSeasonProfile,
        ClubSeasonProfileStatus,
    )

    profile = db.execute(
        select(ClubSeasonProfile).where(
            ClubSeasonProfile.club_id == registration.club_id,
            ClubSeasonProfile.season_id == registration.season_id,
        )
    ).scalar_one_or_none()
    submitted_statuses = {
        ClubSeasonProfileStatus.SUBMITTED,
        ClubSeasonProfileStatus.RESUBMITTED,
        ClubSeasonProfileStatus.REVIEWED,
        ClubSeasonProfileStatus.APPROVED,
    }
    if profile is None or profile.status not in submitted_statuses:
        return (
            None,
            "The club's squad list must be submitted to the league"
            " before releasing a player.",
        )

    existing = db.execute(
        select(PlayerRelease).where(
            PlayerRelease.registration_id == data.registration_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None, "A release already exists for this registration."

    release = PlayerRelease(
        registration_id=registration.id,
        player_id=registration.player_id,
        from_club_id=registration.club_id,
        status=ReleaseStatus.PENDING_PLAYER_CONFIRMATION,
        effective_date=data.effective_date,
    )
    db.add(release)
    db.flush()  # get release.id before creating the document

    document = ReleaseDocument(
        release_id=release.id,
        s3_key=data.s3_key,
        file_name=data.file_name,
    )
    db.add(document)
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="release.create",
        entity_type="PlayerRelease",
        entity_id=release.id,
        details={
            "player_id": release.player_id,
            "from_club_id": release.from_club_id,
            "registration_id": data.registration_id,
        },
    )
    db.commit()  # single commit — release + document + audit land together
    db.refresh(release)
    logger.info(
        {
            "event": "create_release.complete",
            "release_id": release.id,
            "player_id": release.player_id,
            "request_id": request_id_var.get(),
        }
    )

    # Notify club admin that a release has been initiated.
    # release.player and release.from_club lazy-load via the still-open session.
    # Note: Player has no email address in this schema — see self-audit for details.
    publish_event(
        "release.initiated",
        {
            "release_id": release.id,
            "player_name": release.player.full_name,
            "club_name": release.from_club.name,
            "recipient_email": release.from_club.email,
        },
    )

    return release, None


def decide_release(
    db: Session,
    release: PlayerRelease,
    decision: str,
    current_user: CurrentUser,
) -> tuple[PlayerRelease | None, str | None]:
    """
    Guards:
      - current_user must be the player named in the release
      - release must still be PENDING_PLAYER_CONFIRMATION
    On confirm: atomically marks release CONFIRMED + registration RELEASED.
    On reject: marks release REJECTED only.
    """
    logger.info(
        {
            "event": "decide_release.start",
            "release_id": release.id,
            "decision": decision,
            "request_id": request_id_var.get(),
        }
    )
    if current_user.player_id != release.player_id:
        return None, "Only the player being released can decide on this release."

    if release.status != ReleaseStatus.PENDING_PLAYER_CONFIRMATION:
        return None, "This release has already been processed."

    now = datetime.now(tz=UTC)

    # confirm — update both release and registration atomically
    release.status = ReleaseStatus.CONFIRMED
    release.confirmed_at = now
    registration = db.get(PlayerSeasonRegistration, release.registration_id)
    registration.status = PlayerSeasonRegistrationStatus.RELEASED  # type: ignore[union-attr]
    registration.released_at = now  # type: ignore[union-attr]
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="release.confirm",
        entity_type="PlayerRelease",
        entity_id=release.id,
    )
    db.commit()  # single commit — both changes land together or neither does
    db.refresh(release)
    logger.info(
        {
            "event": "decide_release.complete",
            "release_id": release.id,
            "outcome": "confirmed",
            "request_id": request_id_var.get(),
        }
    )
    publish_event(
        "release.confirmed",
        {
            "release_id": release.id,
            "player_name": release.player.full_name,
            "club_name": release.from_club.name,
            "recipient_email": release.from_club.email,
        },
    )
    return release, None
