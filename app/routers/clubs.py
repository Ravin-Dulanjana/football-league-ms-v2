from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.club import Club
from app.schemas.club import ClubRead
from app.services import club_service

router = APIRouter(prefix="/clubs", tags=["clubs"])


@router.get("/", response_model=list[ClubRead])
def list_clubs(db: Session = Depends(get_db)) -> list[Club]:
    return club_service.get_all_clubs(db)
