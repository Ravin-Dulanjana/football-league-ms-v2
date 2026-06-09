from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.club import Club
from app.schemas.club import ClubCreate, ClubRead, ClubUpdate, UploadUrlResponse
from app.services import club_service, storage

router = APIRouter(prefix="/clubs", tags=["clubs"])

_DUPLICATE_MSG = "A club with that name or code already exists."


@router.get("/", response_model=list[ClubRead])
def list_clubs(db: Session = Depends(get_db)) -> list[Club]:
    return club_service.get_all_clubs(db)


@router.post("/", response_model=ClubRead, status_code=status.HTTP_201_CREATED)
def create_club(data: ClubCreate, db: Session = Depends(get_db)) -> Club:
    try:
        return club_service.create_club(db, data)
    except IntegrityError as err:
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE_MSG) from err


@router.get("/{club_id}/", response_model=ClubRead)
def get_club(club_id: int, db: Session = Depends(get_db)) -> Club:
    club = club_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Club not found.")
    return club


@router.patch("/{club_id}/", response_model=ClubRead)
def update_club(club_id: int, data: ClubUpdate, db: Session = Depends(get_db)) -> Club:
    club = club_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Club not found.")
    try:
        return club_service.update_club(db, club, data)
    except IntegrityError as err:
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE_MSG) from err


@router.post(
    "/{club_id}/logo-upload-url/",
    response_model=UploadUrlResponse,
    summary="Get a pre-signed URL to upload a club logo directly to S3",
)
def get_logo_upload_url(
    club_id: int,
    filename: str,
    content_type: str = "image/jpeg",
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Returns a pre-signed POST URL and form fields.

    Upload flow:
    1. Call this endpoint to get the URL, fields, and key.
    2. POST the file directly to S3:
           POST {url}
           multipart/form-data: {all fields from "fields"}, file=<bytes>
       Important: all fields MUST appear in the form BEFORE the file field.
    3. On HTTP 204 from S3, call PATCH /clubs/{id}/ with {"logo_key": "<key>"}.

    The URL expires in 900 seconds (15 minutes).
    Max file size: 10 MB.
    """
    club = club_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Club not found.")

    return storage.generate_upload_url(
        folder=f"clubs/{club_id}/logos",
        filename=filename,
        content_type=content_type,
    )
