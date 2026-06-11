from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    club_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Player]:
    """
    Returns player profiles only (not club_staff).
    club_admin callers are automatically scoped to their own club.
    """
    effective_club_id = club_id
    if current_user.role == "club_admin" and current_user.club_id:
        effective_club_id = current_user.club_id
    if effective_club_id is not None:
        return player_service.get_all_players(db, club_id=effective_club_id)
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
    current_user: CurrentUser = Depends(get_current_user),
) -> Player:
    """
    Update a player profile.

    Admins (super_admin, league_admin, club_admin) may update any player.
    A player may update their own profile (identified by current_user.player_id).
    """
    is_admin = current_user.role in ("super_admin", "league_admin", "club_admin")
    is_own_profile = current_user.player_id == player_id
    if not is_admin and not is_own_profile:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can only update your own player profile.",
        )
    player = player_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found.")
    return player_service.update_player(db, player, data)


@router.post(
    "/me/photo-upload-url/",
    response_model=UploadUrlResponse,
    summary="Get a pre-signed URL to upload your own profile photo",
)
def get_my_photo_upload_url(
    filename: str,
    content_type: str = "image/jpeg",
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    """
    Get a pre-signed URL to upload the current user's own profile photo.
    The user must have a linked player profile (player_id is not null).
    """
    if not current_user.player_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No player profile linked to your account.",
        )
    return storage.generate_upload_url(
        folder=f"players/{current_user.player_id}/photos",
        filename=filename,
        content_type=content_type,
    )


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
