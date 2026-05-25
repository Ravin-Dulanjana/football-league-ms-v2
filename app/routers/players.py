from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.player import Player
from app.schemas.player import PlayerCreate, PlayerRead, PlayerUpdate
from app.services import player_service

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/", response_model=list[PlayerRead])
def list_players(db: Session = Depends(get_db)) -> list[Player]:
    return player_service.get_all_players(db)


@router.post("/", response_model=PlayerRead, status_code=status.HTTP_201_CREATED)
def create_player(data: PlayerCreate, db: Session = Depends(get_db)) -> Player:
    try:
        return player_service.create_player(db, data)
    except IntegrityError as err:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A player with that NIC number already exists."
        ) from err


@router.get("/{player_id}/", response_model=PlayerRead)
def get_player(player_id: int, db: Session = Depends(get_db)) -> Player:
    player = player_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found.")
    return player


@router.patch("/{player_id}/", response_model=PlayerRead)
def update_player(
    player_id: int, data: PlayerUpdate, db: Session = Depends(get_db)
) -> Player:
    player = player_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found.")
    return player_service.update_player(db, player, data)
