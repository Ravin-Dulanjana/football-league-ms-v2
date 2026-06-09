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
from app.schemas.registration import RegistrationRequestCreate
from app.services.events import publish_event

logger = get_logger(__name__)


def get_all_requests(db: Session) -> list[RegistrationRequest]:
    result = db.execute(
        select(RegistrationRequest).order_by(RegistrationRequest.id.desc())
    )
    return list(result.scalars().all())


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

    req = RegistrationRequest(
        season_id=data.season_id,
        club_id=data.club_id,
        player_id=data.player_id,
        requested_by_user_id=current_user.id,
        status=RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    logger.info(
        {
            "event": "create_registration_request.complete",
            "request_id_db": req.id,
            "request_id": request_id_var.get(),
        }
    )

    # Notify club admin that a player wants to join.
    # req.club, req.player, req.season are lazy-loaded here via the still-open
    # session. Fire-and-forget: a SQS outage will not fail the request itself.
    publish_event(
        "registration.requested",
        {
            "registration_request_id": req.id,
            "player_id": req.player_id,
            "player_name": req.player.full_name,
            "club_id": req.club_id,
            "club_name": req.club.name,
            "season_id": req.season_id,
            "season_name": req.season.name,
            "recipient_email": req.club.email,
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
        return None, "Only the requested player can decide on their own registration."

    if req.status != RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION:
        return None, "This request has already been processed."

    now = datetime.now(tz=UTC)

    if decision == "reject":
        req.status = RegistrationRequestStatus.REJECTED
        req.responded_at = now
        db.commit()
        db.refresh(req)
        logger.info(
            {
                "event": "decide_registration_request.complete",
                "request_id_db": req.id,
                "outcome": "rejected",
                "request_id": request_id_var.get(),
            }
        )
        publish_event(
            "registration.rejected",
            {
                "registration_request_id": req.id,
                "player_name": req.player.full_name,
                "club_name": req.club.name,
                "season_name": req.season.name,
                "recipient_email": req.club.email,
            },
        )
        return req, None

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
    publish_event(
        "registration.accepted",
        {
            "registration_request_id": req.id,
            "player_name": req.player.full_name,
            "club_name": req.club.name,
            "season_name": req.season.name,
            "recipient_email": req.club.email,
        },
    )
    return req, None
