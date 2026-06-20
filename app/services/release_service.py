from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser
from app.middleware.logging import get_logger
from app.middleware.request_id import request_id_var
from app.models.player import Player
from app.models.release import (
    PlayerDocument,
    PlayerRelease,
    ReleaseDocument,
    ReleaseStatus,
)
from app.models.season import Season
from app.models.user import User
from app.schemas.release import PlayerDocumentCreate, ReleaseCreate
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
      everyone else with a player_id — only their own releases
      super admin / no player — everything
    """
    q = select(PlayerRelease).order_by(PlayerRelease.id.desc())
    if current_user is not None:
        if current_user.role == "club_admin" and current_user.club_id:
            q = q.where(PlayerRelease.from_club_id == current_user.club_id)
        elif current_user.player_id:
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
    Club admin releases a player from their club, with a required PDF document.

    Guards:
      - caller must have a club (club_id is not None)
      - player must exist and be in the caller's club
      - no active season (roster is locked while a season is in progress)

    On success:
      - PlayerRelease (status=CONFIRMED) + ReleaseDocument are created atomically
      - player.club_id and linked user.club_id are cleared immediately
    """
    logger.info(
        {
            "event": "create_release.start",
            "player_id": data.player_id,
            "request_id": request_id_var.get(),
        }
    )

    if not current_user.club_id:
        return None, "You must be a club admin to release a player."

    player = db.get(Player, data.player_id)
    if player is None:
        return None, "Player not found."
    if player.club_id != current_user.club_id:
        return None, "You can only release players from your own club."

    seasons = list(
        db.execute(select(Season).where(Season.is_archived.is_(False))).scalars().all()
    )
    if any(s.is_locked for s in seasons):
        return None, (
            "Cannot release a player while a season is active. "
            "Releases are only allowed outside of the playing season."
        )

    now = datetime.now(tz=UTC)

    release = PlayerRelease(
        player_id=player.id,
        from_club_id=current_user.club_id,
        status=ReleaseStatus.CONFIRMED,
        confirmed_at=now,
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

    # Clear club membership immediately
    player.club_id = None
    linked_user = db.execute(
        select(User).where(User.player_id == player.id)
    ).scalar_one_or_none()
    if linked_user is not None:
        linked_user.club_id = None

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
        },
    )
    db.commit()
    db.refresh(release)
    logger.info(
        {
            "event": "create_release.complete",
            "release_id": release.id,
            "player_id": release.player_id,
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


def decide_release(
    db: Session,
    release: PlayerRelease,
    decision: str,
    current_user: CurrentUser,
) -> tuple[PlayerRelease | None, str | None]:
    """
    Legacy endpoint: kept for old PENDING_PLAYER_CONFIRMATION records.
    New releases are created with status=CONFIRMED directly.
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
    release.status = ReleaseStatus.CONFIRMED
    release.confirmed_at = now

    if release.registration_id is not None:
        from app.models.registration import (  # noqa: PLC0415
            PlayerSeasonRegistration,
            PlayerSeasonRegistrationStatus,
        )

        registration = db.get(PlayerSeasonRegistration, release.registration_id)
        if registration is not None:
            registration.status = PlayerSeasonRegistrationStatus.RELEASED
            registration.released_at = now

    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="release.confirm",
        entity_type="PlayerRelease",
        entity_id=release.id,
    )
    db.commit()
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


# ---------------------------------------------------------------------------
# Player self-uploaded documents
# ---------------------------------------------------------------------------


def get_player_documents(db: Session, player_id: int) -> list[PlayerDocument]:
    return list(
        db.execute(
            select(PlayerDocument)
            .where(PlayerDocument.player_id == player_id)
            .order_by(PlayerDocument.id.desc())
        )
        .scalars()
        .all()
    )


def create_player_document(
    db: Session,
    player_id: int,
    data: PlayerDocumentCreate,
    current_user: CurrentUser,
) -> PlayerDocument:
    doc = PlayerDocument(
        player_id=player_id,
        s3_key=data.s3_key,
        file_name=data.file_name,
        description=data.description,
    )
    db.add(doc)
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="player_document.create",
        entity_type="PlayerDocument",
        entity_id=doc.id,
        details={"player_id": player_id, "file_name": data.file_name},
    )
    db.commit()
    db.refresh(doc)
    return doc
