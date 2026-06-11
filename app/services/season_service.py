from __future__ import annotations

import traceback

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser
from app.middleware.logging import get_logger
from app.middleware.request_id import request_id_var
from app.models.season import Season, SeasonStatus
from app.schemas.season import SeasonCreate, SeasonUpdate
from app.services import audit_service, notification_service

logger = get_logger(__name__)


def is_registration_window_open(season: Season) -> bool:
    return season.status == SeasonStatus.OPEN


def is_roster_locked(season: Season) -> bool:
    return season.status == SeasonStatus.ACTIVE


def transfers_allowed(season: Season) -> bool:
    return season.status in (SeasonStatus.CLOSED, SeasonStatus.DRAFT)


def get_all_seasons(db: Session) -> list[Season]:
    result = db.execute(select(Season).order_by(Season.year.desc()))
    return list(result.scalars().all())


def get_season_by_id(db: Session, season_id: int) -> Season | None:
    return db.get(Season, season_id)


def _bump_season_cache() -> None:
    # TODO: implement with Redis INCR on a namespace version key.
    pass


def create_season(db: Session, data: SeasonCreate, current_user: CurrentUser) -> Season:
    logger.info(
        {
            "event": "create_season.start",
            "year": data.year,
            "request_id": request_id_var.get(),
        }
    )
    season = Season(**data.model_dump())
    db.add(season)
    try:
        db.flush()
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

    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="season.create",
        entity_type="Season",
        entity_id=season.id,
        details={"year": data.year, "name": data.name},
    )
    notification_service.notify_by_role(
        db,
        role="club_admin",
        event_type="season.created",
        message=f"A new season '{season.name}' ({season.year}) has been created.",
    )
    db.commit()
    db.refresh(season)
    logger.info(
        {
            "event": "create_season.complete",
            "season_id": season.id,
            "request_id": request_id_var.get(),
        }
    )
    _bump_season_cache()
    return season


def update_season(
    db: Session, season: Season, data: SeasonUpdate, current_user: CurrentUser
) -> tuple[Season, str | None]:
    logger.info(
        {
            "event": "update_season.start",
            "season_id": season.id,
            "request_id": request_id_var.get(),
        }
    )
    updates = data.model_dump(exclude_unset=True)
    was_archived = season.is_archived

    for field, value in updates.items():
        setattr(season, field, value)

    db.flush()

    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="season.update",
        entity_type="Season",
        entity_id=season.id,
        details=updates,
    )

    if updates.get("is_archived") and not was_archived:
        notification_service.notify_by_role(
            db,
            role="club_admin",
            event_type="season.archived",
            message=f"Season '{season.name}' ({season.year}) has been archived.",
        )

    db.commit()
    db.refresh(season)
    logger.info(
        {
            "event": "update_season.complete",
            "season_id": season.id,
            "request_id": request_id_var.get(),
        }
    )
    _bump_season_cache()
    return season, None


def delete_season(
    db: Session, season: Season, current_user: CurrentUser
) -> tuple[bool, str | None]:
    """
    Permanently delete a season and all associated data.

    Only allowed for DRAFT or ARCHIVED seasons (never when players have
    active registrations).  Cascades to registration_requests,
    player_season_registrations, and club_season_profiles via FK ON DELETE CASCADE.
    """
    if season.status not in (SeasonStatus.DRAFT, SeasonStatus.ARCHIVED):
        return False, (
            f"Cannot delete a season in '{season.status}' status. "
            "Only draft or archived seasons may be deleted."
        )

    season_id = season.id
    season_name = season.name
    db.delete(season)
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="season.delete",
        entity_type="Season",
        entity_id=season_id,
        details={"name": season_name},
    )
    db.commit()
    logger.info(
        {
            "event": "delete_season.complete",
            "season_id": season_id,
            "request_id": request_id_var.get(),
        }
    )
    _bump_season_cache()
    return True, None
