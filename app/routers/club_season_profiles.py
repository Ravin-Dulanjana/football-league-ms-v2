"""
ClubSeasonProfile endpoints.

GET  /club-season-profiles/              — authenticated, scoped by role
POST /club-season-profiles/              — club_admin for their club or super_admin
POST /club-season-profiles/{id}/submit/  — club_admin for this club or super_admin
POST /club-season-profiles/{id}/transition/ — league_admin or super_admin
GET  /club-season-profiles/{id}/comments/   — scoped by role
POST /club-season-profiles/{id}/comments/   — scoped by role
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user
from app.dependencies.roles import require_any_admin, require_league_admin_or_above
from app.models.club_season import ClubSeasonComment, ClubSeasonProfile
from app.schemas.club_season import (
    ClubSeasonProfileCreate,
    ClubSeasonProfileRead,
    ClubSeasonProfileTransition,
    CommentCreate,
    CommentRead,
)
from app.services import club_season_service
from app.services.role_checks import can_manage_club

router = APIRouter(prefix="/club-season-profiles", tags=["club-season-profiles"])


@router.get("/", response_model=list[ClubSeasonProfileRead])
def list_profiles(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ClubSeasonProfile]:
    return club_season_service.get_profiles(db, current_user)


@router.post(
    "/", response_model=ClubSeasonProfileRead, status_code=status.HTTP_201_CREATED
)
def create_profile(
    data: ClubSeasonProfileCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_any_admin),
) -> ClubSeasonProfile:
    # club_admin can only create profiles for their own club
    if current_user.role == "club_admin" and data.club_id != current_user.club_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Club admins can only create profiles for their own club.",
        )
    profile, error = club_season_service.create_profile(db, data, current_user)
    if error:
        raise HTTPException(status.HTTP_409_CONFLICT, error)
    return profile  # type: ignore[return-value]


@router.post("/{profile_id}/submit/", response_model=ClubSeasonProfileRead)
def submit_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ClubSeasonProfile:
    profile = club_season_service.get_profile_by_id(db, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found.")

    # Only super_admin or the club's own admin may submit
    if not (
        current_user.role == "super_admin"
        or can_manage_club(current_user, profile.club_id)
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You cannot submit this club's profile.",
        )

    updated, error = club_season_service.submit_profile(db, profile, current_user)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return updated  # type: ignore[return-value]


@router.post("/{profile_id}/transition/", response_model=ClubSeasonProfileRead)
def transition_profile(
    profile_id: int,
    data: ClubSeasonProfileTransition,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_league_admin_or_above),
) -> ClubSeasonProfile:
    profile = club_season_service.get_profile_by_id(db, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found.")

    updated, error = club_season_service.transition_profile(
        db, profile, data, current_user
    )
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return updated  # type: ignore[return-value]


@router.get("/{profile_id}/comments/", response_model=list[CommentRead])
def list_comments(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ClubSeasonComment]:
    profile = club_season_service.get_profile_by_id(db, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found.")
    # club_admin can only view comments for their own club's profile
    if current_user.role == "club_admin" and profile.club_id != current_user.club_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You cannot view comments on this profile."
        )
    return club_season_service.get_comments(db, profile_id, current_user)


@router.post(
    "/{profile_id}/comments/",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    profile_id: int,
    data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ClubSeasonComment:
    profile = club_season_service.get_profile_by_id(db, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found.")
    # club_admin may comment on their own club's profile only
    if current_user.role == "club_admin" and profile.club_id != current_user.club_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You cannot comment on this profile."
        )
    comment, error = club_season_service.add_comment(db, profile_id, data, current_user)
    if error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, error)
    return comment  # type: ignore[return-value]
