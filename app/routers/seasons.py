from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user, require_role
from app.models.season import Season
from app.schemas.season import SeasonCreate, SeasonRead, SeasonUpdate
from app.services import season_service

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("/", response_model=list[SeasonRead])
def list_seasons(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[Season]:
    return season_service.get_all_seasons(db)


@router.post("/", response_model=SeasonRead, status_code=status.HTTP_201_CREATED)
def create_season(
    data: SeasonCreate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_role("super_admin", "league_admin")),
) -> Season:
    try:
        return season_service.create_season(db, data)
    except IntegrityError as err:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A season for that year already exists."
        ) from err


@router.patch("/{season_id}/", response_model=SeasonRead)
def update_season(
    season_id: int,
    data: SeasonUpdate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_role("super_admin", "league_admin")),
) -> Season:
    season = season_service.get_season_by_id(db, season_id)
    if season is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Season not found.")
    updated, error = season_service.update_season(db, season, data)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return updated
