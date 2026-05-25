from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.club import Club, ClubStatus


def get_all_clubs(db: Session) -> list[Club]:
    result = db.execute(select(Club).where(Club.status == ClubStatus.ACTIVE))
    return list(result.scalars().all())
