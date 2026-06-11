"""
League info endpoints.

GET  /league-info/   — any authenticated user
PUT  /league-info/   — league_admin and super_admin only
POST /league-info/logo-upload-url/ — league_admin and super_admin only
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user
from app.dependencies.roles import require_league_admin_or_above
from app.models.league_info import LeagueInfo
from app.schemas.league_info import LeagueInfoRead, LeagueInfoUpdate
from app.services import storage

router = APIRouter(prefix="/league-info", tags=["league-info"])

SINGLETON_ID = 1


def _get_or_create(db: Session) -> LeagueInfo:
    """Return the singleton row, creating it if it doesn't exist yet."""
    row = db.get(LeagueInfo, SINGLETON_ID)
    if row is None:
        row = LeagueInfo(id=SINGLETON_ID, league_name="")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/", response_model=LeagueInfoRead)
def get_league_info(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> LeagueInfo:
    return _get_or_create(db)


@router.put("/", response_model=LeagueInfoRead)
def update_league_info(
    data: LeagueInfoUpdate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_league_admin_or_above),
) -> LeagueInfo:
    row = _get_or_create(db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.flush()
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/logo-upload-url/",
    summary="Get a pre-signed URL to upload the league logo directly to S3",
)
def get_logo_upload_url(
    filename: str,
    content_type: str = "image/jpeg",
    _: CurrentUser = Depends(require_league_admin_or_above),
) -> dict[str, object]:
    """
    Returns a pre-signed POST URL and form fields for league logo upload.

    Upload flow:
    1. Call this endpoint to get the URL, fields, and key.
    2. POST the file directly to S3 using the returned URL and fields.
    3. On HTTP 204 from S3, call PUT /league-info/ with {"logo_key": "<key>"}.

    The URL expires in 900 seconds (15 minutes). Max file size: 10 MB.
    """
    if not storage:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Storage not configured.",
        )
    return storage.generate_upload_url(
        folder="league/logos",
        filename=filename,
        content_type=content_type,
    )
