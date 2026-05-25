from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user
from app.models.release import PlayerRelease
from app.schemas.release import ReleaseCreate, ReleaseDecide, ReleaseRead
from app.services import release_service

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("/", response_model=list[ReleaseRead])
def list_releases(db: Session = Depends(get_db)) -> list[PlayerRelease]:
    return release_service.get_all_releases(db)


@router.post("/", response_model=ReleaseRead, status_code=status.HTTP_201_CREATED)
def create_release(
    data: ReleaseCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlayerRelease:
    release, error = release_service.create_release(db, data, current_user)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return release  # type: ignore[return-value]


@router.post("/{release_id}/decide/", response_model=ReleaseRead)
def decide_release(
    release_id: int,
    data: ReleaseDecide,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlayerRelease:
    release = release_service.get_release_by_id(db, release_id)
    if release is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Release not found.")
    updated, error = release_service.decide_release(
        db, release, data.decision, current_user
    )
    if error:
        code = (
            status.HTTP_403_FORBIDDEN
            if "Only the" in error
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, error)
    return updated  # type: ignore[return-value]
