from __future__ import annotations

import traceback

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.middleware.logging import get_logger
from app.middleware.request_id import request_id_var
from app.models.club import Club, ClubStatus
from app.schemas.club import ClubCreate, ClubUpdate

logger = get_logger(__name__)


def get_all_clubs(db: Session) -> list[Club]:
    result = db.execute(select(Club).where(Club.status == ClubStatus.ACTIVE))
    return list(result.scalars().all())


def get_club_by_id(db: Session, club_id: int) -> Club | None:
    return db.get(Club, club_id)


def create_club(db: Session, data: ClubCreate) -> Club:
    logger.info({"event": "create_club.start", "request_id": request_id_var.get()})
    club = Club(**data.model_dump())
    db.add(club)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.error(
            {
                "event": "create_club.error",
                "error_type": "IntegrityError",
                "message": "Duplicate club name or code",
                "request_id": request_id_var.get(),
                "stack_trace": traceback.format_exc(),
            }
        )
        raise
    db.refresh(club)
    logger.info(
        {
            "event": "create_club.complete",
            "club_id": club.id,
            "request_id": request_id_var.get(),
        }
    )
    return club


def update_club(db: Session, club: Club, data: ClubUpdate) -> Club:
    logger.info(
        {
            "event": "update_club.start",
            "club_id": club.id,
            "request_id": request_id_var.get(),
        }
    )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(club, field, value)
    db.commit()
    db.refresh(club)
    logger.info(
        {
            "event": "update_club.complete",
            "club_id": club.id,
            "request_id": request_id_var.get(),
        }
    )
    return club
