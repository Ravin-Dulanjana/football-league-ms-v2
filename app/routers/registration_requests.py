from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user, require_role
from app.models.registration import (
    PlayerSeasonRegistration,
    PlayerSeasonRegistrationStatus,
    RegistrationRequest,
)
from app.schemas.registration import (
    PlayerSeasonRegistrationRead,
    RegistrationDecide,
    RegistrationRequestCreate,
    RegistrationRequestRead,
)
from app.services import registration_service

router = APIRouter(prefix="/registration-requests", tags=["registration-requests"])


@router.get("/", response_model=list[RegistrationRequestRead])
def list_requests(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RegistrationRequest]:
    """
    Returns registration requests scoped by caller role:
    - club_admin: only their own club's requests
    - player: only requests for their own player_id
    - league_admin / super_admin: all requests
    """
    return registration_service.get_all_requests(db, current_user)


@router.post(
    "/", response_model=RegistrationRequestRead, status_code=status.HTTP_201_CREATED
)
def create_request(
    data: RegistrationRequestCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_role("super_admin", "league_admin", "club_admin")
    ),
) -> RegistrationRequest:
    if current_user.role == "club_admin" and data.club_id != current_user.club_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Club admins can only create registration requests for their own club.",
        )
    req, error = registration_service.create_request(db, data, current_user)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return req  # type: ignore[return-value]


@router.post("/{request_id}/decide/", response_model=RegistrationRequestRead)
def decide_request(
    request_id: int,
    data: RegistrationDecide,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("player")),
) -> RegistrationRequest:
    req = registration_service.get_request_by_id(db, request_id)
    if req is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Registration request not found."
        )
    updated, error = registration_service.decide_request(
        db, req, data.decision, current_user
    )
    if error:
        code = (
            status.HTTP_403_FORBIDDEN
            if "Only the" in error
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, error)
    return updated  # type: ignore[return-value]


@router.get(
    "/player-season-registrations/",
    response_model=list[PlayerSeasonRegistrationRead],
)
def list_player_season_registrations(
    club_id: int | None = None,
    season_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PlayerSeasonRegistration]:
    """
    Active PlayerSeasonRegistrations, optionally filtered by club and/or season.
    Club admins are restricted to their own club.
    """
    q = select(PlayerSeasonRegistration).where(
        PlayerSeasonRegistration.status == PlayerSeasonRegistrationStatus.ACTIVE
    )
    if current_user.role == "club_admin":
        q = q.where(PlayerSeasonRegistration.club_id == current_user.club_id)
    elif club_id is not None:
        q = q.where(PlayerSeasonRegistration.club_id == club_id)

    if season_id is not None:
        q = q.where(PlayerSeasonRegistration.season_id == season_id)

    q = q.order_by(PlayerSeasonRegistration.id.asc())
    return list(db.execute(q).scalars().all())
