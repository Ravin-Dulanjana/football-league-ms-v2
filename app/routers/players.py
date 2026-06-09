from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user, require_role
from app.models.player import Player
from app.schemas.club import UploadUrlResponse
from app.schemas.player import PlayerCreate, PlayerRead, PlayerUpdate
from app.services import player_service, storage

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/", response_model=list[PlayerRead])
def list_players(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),  # any authenticated user
) -> list[Player]:
    return player_service.get_all_players(db)


@router.post("/", response_model=PlayerRead, status_code=status.HTTP_201_CREATED)
def create_player(
    data: PlayerCreate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_role("super_admin", "league_admin", "club_admin")),
) -> Player:
    try:
        return player_service.create_player(db, data)
    except IntegrityError as err:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A player with that NIC number already exists."
        ) from err


@router.get("/{player_id}/", response_model=PlayerRead)
def get_player(
    player_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> Player:
    player = player_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found.")
    return player


@router.patch("/{player_id}/", response_model=PlayerRead)
def update_player(
    player_id: int,
    data: PlayerUpdate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_role("super_admin", "league_admin", "club_admin")),
) -> Player:
    player = player_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found.")
    return player_service.update_player(db, player, data)


@router.post(
    "/{player_id}/photo-upload-url/",
    response_model=UploadUrlResponse,
    summary="Get a pre-signed URL to upload a player photo directly to S3",
)
def get_photo_upload_url(
    player_id: int,
    filename: str,
    content_type: str = "image/jpeg",
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Returns a pre-signed POST URL and form fields.

    Upload flow:
    1. Call this endpoint to get the URL, fields, and key.
    2. POST the file directly to S3 (never through the API).
    3. On HTTP 204 from S3, call PATCH /players/{id}/ with {"photo_key": "<key>"}.

    The URL expires in 900 seconds (15 minutes). Max file size: 10 MB.
    """
    player = player_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found.")

    return storage.generate_upload_url(
        folder=f"players/{player_id}/photos",
        filename=filename,
        content_type=content_type,
    )
