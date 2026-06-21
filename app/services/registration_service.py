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
    RegistrationRequest,
    RegistrationRequestStatus,
    RegistrationType,
)
from app.models.user import User
from app.schemas.registration import RegistrationRequestCreate
from app.services import audit_service
from app.services.events import publish_event
from app.services.notification_service import notify_club_admins, notify_user

logger = get_logger(__name__)


def get_all_requests(
    db: Session,
    current_user: CurrentUser | None = None,
) -> list[RegistrationRequest]:
    """
    Return registration requests scoped by caller role:
      club_admin  — only their club's requests
      player      — only requests for their own player_id
      all others  — everything
    """
    q = select(RegistrationRequest).order_by(RegistrationRequest.id.desc())
    if current_user is not None:
        if current_user.role == "club_admin" and current_user.club_id:
            q = q.where(RegistrationRequest.club_id == current_user.club_id)
        elif current_user.role == "player" and current_user.player_id:
            q = q.where(RegistrationRequest.player_id == current_user.player_id)
    return list(db.execute(q).scalars().all())


def get_request_by_id(db: Session, request_id: int) -> RegistrationRequest | None:
    return db.get(RegistrationRequest, request_id)


def create_request(
    db: Session,
    data: RegistrationRequestCreate,
    current_user: CurrentUser,
) -> tuple[RegistrationRequest | None, str | None]:
    """
    Returns (registration_request, error_message).
    Guards:
      - registration window must be open
      - player must not already have a registration this season
    """
    logger.info(
        {
            "event": "create_registration_request.start",
            "player_id": data.player_id,
            "season_id": data.season_id,
            "club_id": data.club_id,
            "request_id": request_id_var.get(),
        }
    )
    from app.models.season import Season
    from app.services.season_service import is_registration_window_open

    season = db.get(Season, data.season_id)
    if season is None:
        return None, "Season not found."
    if not is_registration_window_open(season):
        return None, "Registration window is not open for this season."

    existing = db.execute(
        select(PlayerSeasonRegistration).where(
            PlayerSeasonRegistration.player_id == data.player_id,
            PlayerSeasonRegistration.season_id == data.season_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None, "Player already has a registration in this season."

    # Cap: at most 30 players per club per season (pending + accepted combined)
    from app.models.registration import RegistrationRequestStatus  # noqa: PLC0415

    squad_count = (
        db.execute(
            select(RegistrationRequest).where(
                RegistrationRequest.club_id == data.club_id,
                RegistrationRequest.season_id == data.season_id,
                RegistrationRequest.status.in_(
                    [
                        RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION,
                        RegistrationRequestStatus.ACCEPTED,
                    ]
                ),
            )
        )
        .scalars()
        .all()
    )
    if len(squad_count) >= 30:
        return None, "Maximum of 30 players per club per season already reached."

    # Look up the player's linked user for in-app notification and email.
    player_user = db.execute(
        select(User).where(User.player_id == data.player_id)
    ).scalar_one_or_none()

    req = RegistrationRequest(
        season_id=data.season_id,
        club_id=data.club_id,
        player_id=data.player_id,
        requested_by_user_id=current_user.id,
        status=RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(req)
    db.flush()  # get req.id before writing audit log
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="registration_request.create",
        entity_type="RegistrationRequest",
        entity_id=req.id,
        details={
            "player_id": data.player_id,
            "club_id": data.club_id,
            "season_id": data.season_id,
        },
    )
    # Capture names before commit expires relationships.
    club_name = req.club.name
    season_name = req.season.name
    player_name = req.player.full_name
    if player_user is not None:
        notify_user(
            db,
            user_id=player_user.id,
            event_type="registration.requested",
            message=(
                f"You have been added to {club_name}'s squad for {season_name}. "
                "Log in to acknowledge your registration."
            ),
        )
    db.commit()
    db.refresh(req)
    logger.info(
        {
            "event": "create_registration_request.complete",
            "request_id_db": req.id,
            "request_id": request_id_var.get(),
        }
    )

    # Email the player — they need to acknowledge the request.
    publish_event(
        "registration.requested",
        {
            "registration_request_id": req.id,
            "player_id": data.player_id,
            "player_name": player_name,
            "club_id": data.club_id,
            "club_name": club_name,
            "season_id": data.season_id,
            "season_name": season_name,
            "recipient_email": player_user.email if player_user else None,
        },
    )

    return req, None


def decide_request(
    db: Session,
    req: RegistrationRequest,
    decision: str,
    current_user: CurrentUser,
) -> tuple[RegistrationRequest | None, str | None]:
    """
    Guards:
      - current_user must be the player named in the request
      - request must still be PENDING_PLAYER_CONFIRMATION
    On accept: atomically creates PlayerSeasonRegistration + marks request ACCEPTED.
    On reject: marks request REJECTED.
    """
    logger.info(
        {
            "event": "decide_registration_request.start",
            "request_id_db": req.id,
            "decision": decision,
            "request_id": request_id_var.get(),
        }
    )
    if current_user.player_id != req.player_id:
        return None, "Only the requested player can acknowledge their own registration."

    if req.status != RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION:
        return None, "This request has already been processed."

    now = datetime.now(tz=UTC)

    # Capture names before any flush/commit expires relationships.
    player_name = req.player.full_name
    club_name = req.club.name
    season_name = req.season.name
    club_email = req.club.email
    club_id = req.club_id

    # accept — create registration atomically
    req.status = RegistrationRequestStatus.ACCEPTED
    req.responded_at = now
    registration = PlayerSeasonRegistration(
        season_id=req.season_id,
        club_id=req.club_id,
        player_id=req.player_id,
        registration_type=RegistrationType.NEW,
        status=PlayerSeasonRegistrationStatus.ACTIVE,
    )
    db.add(registration)
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="registration_request.accept",
        entity_type="RegistrationRequest",
        entity_id=req.id,
    )
    notify_club_admins(
        db,
        club_id=club_id,
        event_type="registration.accepted",
        message=(
            f"{player_name} has acknowledged their squad registration for "
            f"{club_name} in {season_name}."
        ),
    )
    db.commit()  # single commit — both changes land together or neither does
    db.refresh(req)
    logger.info(
        {
            "event": "decide_registration_request.complete",
            "request_id_db": req.id,
            "outcome": "accepted",
            "request_id": request_id_var.get(),
        }
    )
    # Email the club (contact address) that the player acknowledged.
    publish_event(
        "registration.accepted",
        {
            "registration_request_id": req.id,
            "player_name": player_name,
            "club_name": club_name,
            "season_name": season_name,
            "recipient_email": club_email,
        },
    )
    return req, None
