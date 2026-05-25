from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.player import Player
from app.schemas.player import PlayerCreate, PlayerUpdate


def get_all_players(db: Session) -> list[Player]:
    result = db.execute(select(Player).order_by(Player.id))
    return list(result.scalars().all())


def get_player_by_id(db: Session, player_id: int) -> Player | None:
    return db.get(Player, player_id)


def create_player(db: Session, data: PlayerCreate) -> Player:
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
        raise
    db.refresh(player)
    return player


def update_player(db: Session, player: Player, data: PlayerUpdate) -> Player:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(player, field, value)
    player.updated_at = datetime.now(tz=UTC)
    db.commit()
    db.refresh(player)
    return player
