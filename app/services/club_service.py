from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.club import Club, ClubStatus
from app.schemas.club import ClubCreate, ClubUpdate


def get_all_clubs(db: Session) -> list[Club]:
    result = db.execute(select(Club).where(Club.status == ClubStatus.ACTIVE))
    return list(result.scalars().all())


def get_club_by_id(db: Session, club_id: int) -> Club | None:
    return db.get(Club, club_id)


def create_club(db: Session, data: ClubCreate) -> Club:
    club = Club(**data.model_dump())
    db.add(club)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(club)
    return club


def update_club(db: Session, club: Club, data: ClubUpdate) -> Club:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(club, field, value)
    db.commit()
    db.refresh(club)
    return club
