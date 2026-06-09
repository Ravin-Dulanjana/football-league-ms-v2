"""
ClubStaff endpoints.

GET  /club-staff/        — authenticated, scoped by role
POST /club-staff/        — club_admin for their club or super_admin
DELETE /club-staff/{id}/ — club_admin for their club or super_admin
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user
from app.models.club_season import ClubStaff
from app.schemas.club_season import ClubStaffCreate, ClubStaffRead
from app.services import club_season_service
from app.services.role_checks import can_manage_club

router = APIRouter(prefix="/club-staff", tags=["club-staff"])


@router.get("/", response_model=list[ClubStaffRead])
def list_staff(
    club_id: int | None = Query(None),
    season_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ClubStaff]:
    return club_season_service.get_staff(db, current_user, club_id, season_id)


@router.post("/", response_model=ClubStaffRead, status_code=status.HTTP_201_CREATED)
def add_staff(
    data: ClubStaffCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ClubStaff:
    if not can_manage_club(current_user, data.club_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You cannot add staff to this club.",
        )
    staff, error = club_season_service.add_staff(db, data, current_user)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return staff  # type: ignore[return-value]


@router.delete("/{staff_id}/", status_code=status.HTTP_204_NO_CONTENT)
def remove_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    staff = db.get(ClubStaff, staff_id)
    if staff is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff record not found.")
    if not can_manage_club(current_user, staff.club_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You cannot remove staff from this club.",
        )
    _, error = club_season_service.remove_staff(db, staff, current_user)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
