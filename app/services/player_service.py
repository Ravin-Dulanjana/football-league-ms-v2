from __future__ import annotations

import traceback
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.middleware.logging import get_logger
from app.middleware.request_id import request_id_var
from app.models.player import Player
from app.schemas.player import PlayerCreate, PlayerUpdate

logger = get_logger(__name__)


def get_all_players(db: Session) -> list[Player]:
    result = db.execute(select(Player).order_by(Player.id))
    return list(result.scalars().all())


def get_player_by_id(db: Session, player_id: int) -> Player | None:
    return db.get(Player, player_id)


def create_player(db: Session, data: PlayerCreate) -> Player:
    # ⚠️  NEVER log data.nic_number — it is a personal identifier.
    logger.info(
        {
            "event": "create_player.start",
            "full_name": data.full_name,
            "request_id": request_id_var.get(),
        }
    )
    player = Player(
        league_player_code="PENDING",  # replaced after flush gives us the id
        **data.model_dump(),
    )
    db.add(player)
    try:
        db.flush()  # populate player.id without committing
        player.league_player_code = f"WL-{player.id:04d}"
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.error(
            {
                "event": "create_player.error",
                "error_type": "IntegrityError",
                "message": "Duplicate NIC or player code",
                "request_id": request_id_var.get(),
                "stack_trace": traceback.format_exc(),
            }
        )
        raise
    db.refresh(player)
    logger.info(
        {
            "event": "create_player.complete",
            "player_id": player.id,
            "league_player_code": player.league_player_code,
            "request_id": request_id_var.get(),
        }
    )
    return player


def update_player(db: Session, player: Player, data: PlayerUpdate) -> Player:
    logger.info(
        {
            "event": "update_player.start",
            "player_id": player.id,
            "request_id": request_id_var.get(),
        }
    )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(player, field, value)
    player.updated_at = datetime.now(tz=UTC)
    db.commit()
    db.refresh(player)
    logger.info(
        {
            "event": "update_player.complete",
            "player_id": player.id,
            "request_id": request_id_var.get(),
        }
    )
    return player
