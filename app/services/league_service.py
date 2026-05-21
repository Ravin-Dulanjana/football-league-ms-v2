from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.league import League


def get_all_leagues(db: Session) -> list[League]:
    result = db.execute(select(League).where(League.is_active.is_(True)))
    return list(result.scalars().all())
