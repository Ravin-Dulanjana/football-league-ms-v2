from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.league import League
from app.schemas.league import LeagueRead
from app.services import league_service

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("/", response_model=list[LeagueRead])
def list_leagues(db: Session = Depends(get_db)) -> list[League]:
    return league_service.get_all_leagues(db)
