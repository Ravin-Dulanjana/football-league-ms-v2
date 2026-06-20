from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user, require_role
from app.models.player import Player
from app.schemas.club import UploadUrlResponse
from app.schemas.player import NicDocumentUpdate, PlayerCreate, PlayerRead, PlayerUpdate
from app.schemas.release import PlayerDocumentCreate, PlayerDocumentRead
from app.services import player_service, release_service, storage

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
    current_user: CurrentUser = Depends(get_current_user),
) -> PlayerRead:
    player = player_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found.")
    result = PlayerRead.model_validate(player)
    if player.nic_document_key and _can_see_nic_document(current_user, player):
        result.nic_document_url = storage.get_file_url(player.nic_document_key)
    return result


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


def _can_see_nic_document(current_user: CurrentUser, player: Player) -> bool:
    """Returns True if caller is allowed to see this player's NIC document URL."""
    if current_user.role in ("super_admin", "league_admin"):
        return True
    if current_user.player_id == player.id:
        return True
    if current_user.role == "club_admin" and current_user.club_id == player.club_id:
        return True
    return False


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


@router.post(
    "/me/nic-upload-url/",
    response_model=UploadUrlResponse,
    summary="Get a pre-signed URL to upload your NIC document PDF",
)
def get_my_nic_upload_url(
    filename: str,
    content_type: str = "application/pdf",
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    if not current_user.player_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No player profile linked to your account.",
        )
    return storage.generate_upload_url(
        folder=f"players/{current_user.player_id}/nic-documents",
        filename=filename,
        content_type=content_type,
    )


@router.patch(
    "/me/nic-document/",
    response_model=PlayerRead,
    summary="Save NIC document key after uploading to S3",
)
def save_my_nic_document(
    data: NicDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlayerRead:
    if not current_user.player_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No player profile linked to your account.",
        )
    player = player_service.get_player_by_id(db, current_user.player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found.")
    player.nic_document_key = data.nic_document_key
    db.commit()
    db.refresh(player)
    result = PlayerRead.model_validate(player)
    result.nic_document_url = storage.get_file_url(player.nic_document_key)
    return result


# ---------------------------------------------------------------------------
# Player documents — self-uploaded external release/transfer docs
# ---------------------------------------------------------------------------


@router.get(
    "/{player_id}/documents/",
    response_model=list[PlayerDocumentRead],
    summary="List external documents uploaded by or for a player",
)
def list_player_documents(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list:
    is_self = current_user.player_id == player_id
    is_admin = current_user.role in ("club_admin", "league_admin", "super_admin")
    if not is_self and not is_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can only view documents for players in your club or your own profile.",
        )
    return release_service.get_player_documents(db, player_id)


@router.post(
    "/me/document-upload-url/",
    response_model=UploadUrlResponse,
    summary="Get a pre-signed URL to upload a personal release/transfer document",
)
def get_my_document_upload_url(
    filename: str,
    content_type: str = "application/pdf",
    _: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    """
    Returns a pre-signed POST URL for uploading a personal document (e.g. an
    external release letter from another league). Upload the file to S3 first,
    then call POST /players/me/documents/ with the returned key.
    """
    return storage.generate_upload_url(
        folder="player-docs",
        filename=filename,
        content_type=content_type,
    )


@router.post(
    "/me/documents/",
    response_model=PlayerDocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Save a personal document record after uploading to S3",
)
def save_my_document(
    data: PlayerDocumentCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> object:
    if not current_user.player_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No player profile linked to your account.",
        )
    return release_service.create_player_document(
        db, current_user.player_id, data, current_user
    )
