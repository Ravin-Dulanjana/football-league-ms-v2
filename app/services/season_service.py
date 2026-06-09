from __future__ import annotations

import traceback
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.middleware.logging import get_logger
from app.middleware.request_id import request_id_var
from app.models.season import Season, SeasonStatus
from app.schemas.season import SeasonCreate, SeasonUpdate

logger = get_logger(__name__)

VALID_TRANSITIONS: dict[SeasonStatus, set[SeasonStatus]] = {
    SeasonStatus.DRAFT: {SeasonStatus.OPEN},
    SeasonStatus.OPEN: {SeasonStatus.CLOSED},
    SeasonStatus.CLOSED: {SeasonStatus.ARCHIVED},
    SeasonStatus.ARCHIVED: set(),
}


def is_registration_window_open(season: Season) -> bool:
    """True when season is OPEN, not locked, and now is within the window.

    SQLite returns naive datetimes from DateTime(timezone=True) columns, while
    PostgreSQL returns tz-aware ones. We normalise by stripping tzinfo when the
    stored values are naive (test / SQLite path) so the comparison always works.
    """
    now = datetime.now(tz=UTC)
    open_at = season.registration_open_at
    close_at = season.registration_close_at
    if open_at.tzinfo is None:
        now = now.replace(tzinfo=None)
    return (
        season.status == SeasonStatus.OPEN
        and not season.is_locked
        and open_at <= now <= close_at
    )


def get_all_seasons(db: Session) -> list[Season]:
    result = db.execute(select(Season).order_by(Season.year.desc()))
    return list(result.scalars().all())


def get_season_by_id(db: Session, season_id: int) -> Season | None:
    return db.get(Season, season_id)


def create_season(db: Session, data: SeasonCreate) -> Season:
    logger.info(
        {
            "event": "create_season.start",
            "year": data.year,
            "request_id": request_id_var.get(),
        }
    )
    season = Season(**data.model_dump(), status=SeasonStatus.DRAFT)
    db.add(season)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.error(
            {
                "event": "create_season.error",
                "error_type": "IntegrityError",
                "message": "Duplicate season year",
                "request_id": request_id_var.get(),
                "stack_trace": traceback.format_exc(),
            }
        )
        raise
    db.refresh(season)
    logger.info(
        {
            "event": "create_season.complete",
            "season_id": season.id,
            "request_id": request_id_var.get(),
        }
    )
    return season


def update_season(
    db: Session, season: Season, data: SeasonUpdate
) -> tuple[Season, str | None]:
    """
    Returns (updated_season, error_message).
    error_message is None on success, a string description on invalid transition.
    """
    logger.info(
        {
            "event": "update_season.start",
            "season_id": season.id,
            "request_id": request_id_var.get(),
        }
    )
    updates = data.model_dump(exclude_unset=True)

    if "status" in updates:
        new_status = updates["status"]
        allowed = VALID_TRANSITIONS[season.status]
        if new_status not in allowed:
            logger.warning(
                {
                    "event": "update_season.invalid_transition",
                    "season_id": season.id,
                    "from_status": season.status,
                    "to_status": new_status,
                    "request_id": request_id_var.get(),
                }
            )
            return season, (
                f"Cannot transition from '{season.status}' to '{new_status}'. "
                f"Allowed: {[s.value for s in allowed] or 'none (terminal state)'}."
            )

    for field, value in updates.items():
        setattr(season, field, value)
    db.commit()
    db.refresh(season)
    logger.info(
        {
            "event": "update_season.complete",
            "season_id": season.id,
            "request_id": request_id_var.get(),
        }
    )
    return season, None
