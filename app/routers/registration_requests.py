from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user, require_role
from app.models.registration import RegistrationRequest
from app.schemas.registration import (
    RegistrationDecide,
    RegistrationRequestCreate,
    RegistrationRequestRead,
)
from app.services import registration_service

router = APIRouter(prefix="/registration-requests", tags=["registration-requests"])


@router.get("/", response_model=list[RegistrationRequestRead])
def list_requests(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[RegistrationRequest]:
    return registration_service.get_all_requests(db)


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
    # Club admins can only create requests for their own club
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
    current_user: CurrentUser = Depends(
        require_role("player", "super_admin", "league_admin")
    ),
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
