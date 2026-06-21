from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser
from app.middleware.logging import get_logger
from app.middleware.request_id import request_id_var
from app.models.club import Club
from app.models.player import Player
from app.models.release import (
    PlayerDocument,
    PlayerRelease,
    ReleaseDocument,
    ReleaseStatus,
)
from app.models.season import Season
from app.models.user import User
from app.models.user_governance_role import UserGovernanceRole
from app.schemas.release import PlayerDocumentCreate, ReleaseCreate
from app.services import audit_service
from app.services.events import publish_event
from app.services.user_service import highest_role

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

    # Auto-create a personal release history entry for the player.
    # year defaults to effective_date year, or current year if no date given.
    from datetime import date as _date

    release_year = (data.effective_date or _date.today()).year
    club = db.get(Club, current_user.club_id)
    personal_doc = PlayerDocument(
        player_id=player.id,
        s3_key=data.s3_key,
        file_name=data.file_name,
        year=release_year,
        league_name="Wattala Football League",
        club_name=club.name if club else None,
        is_visible=True,
        source="in_league",
        release_id=release.id,
    )
    db.add(personal_doc)

    # Clear club membership immediately
    released_from_club_id = current_user.club_id
    player.club_id = None
    linked_user = db.execute(
        select(User).where(User.player_id == player.id)
    ).scalar_one_or_none()
    if linked_user is not None:
        linked_user.club_id = None
        # If the released player is also a club_admin of this club, revoke that role.
        gov_entry = db.execute(
            select(UserGovernanceRole).where(
                UserGovernanceRole.user_id == linked_user.id,
                UserGovernanceRole.role == "club_admin",
                UserGovernanceRole.club_id == released_from_club_id,
            )
        ).scalar_one_or_none()
        if gov_entry is not None:
            db.delete(gov_entry)
            db.flush()
            remaining = list(
                db.execute(
                    select(UserGovernanceRole).where(
                        UserGovernanceRole.user_id == linked_user.id
                    )
                )
                .scalars()
                .all()
            )
            if remaining:
                linked_user.role = highest_role([r.role for r in remaining])
                ca = next((r for r in remaining if r.role == "club_admin"), None)
                linked_user.club_id = ca.club_id if ca else None
            else:
                linked_user.role = linked_user.member_type or "player"
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


def get_player_documents(
    db: Session, player_id: int, *, visible_only: bool = False
) -> list[PlayerDocument]:
    """Return personal release history docs, ordered by year desc then id desc."""
    q = select(PlayerDocument).where(PlayerDocument.player_id == player_id)
    if visible_only:
        q = q.where(PlayerDocument.is_visible.is_(True))
    q = q.order_by(
        PlayerDocument.year.desc().nullslast(),
        PlayerDocument.id.desc(),
    )
    return list(db.execute(q).scalars().all())


def toggle_player_document_visibility(
    db: Session, doc_id: int, current_user: CurrentUser
) -> tuple[PlayerDocument | None, str | None]:
    doc = db.get(PlayerDocument, doc_id)
    if doc is None:
        return None, "Document not found."
    if doc.player_id != current_user.player_id:
        return None, "You can only modify your own documents."
    doc.is_visible = not doc.is_visible
    db.commit()
    db.refresh(doc)
    return doc, None


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
        year=data.year,
        league_name=data.league_name,
        club_name=data.club_name,
        is_visible=True,
        source="manual",
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
