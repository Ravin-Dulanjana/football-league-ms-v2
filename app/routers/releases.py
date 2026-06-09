from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user, require_role
from app.models.release import PlayerRelease
from app.schemas.club import UploadUrlResponse
from app.schemas.release import ReleaseCreate, ReleaseDecide, ReleaseRead
from app.services import release_service, storage

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("/", response_model=list[ReleaseRead])
def list_releases(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[PlayerRelease]:
    return release_service.get_all_releases(db)


@router.post(
    "/document-upload-url/",
    response_model=UploadUrlResponse,
    summary="Get a pre-signed URL to upload a release document directly to S3",
)
def get_document_upload_url(
    filename: str,
    content_type: str = "application/pdf",
) -> dict[str, object]:
    """
    Returns a pre-signed POST URL and form fields for uploading a release document.

    This endpoint does NOT require an existing release ID — the document
    is uploaded first, and the resulting S3 key is submitted alongside
    the release creation payload.

    Upload flow:
    1. Call this endpoint to get the URL, fields, and key.
    2. POST the file directly to S3 (never through the API).
    3. On HTTP 204 from S3, call POST /releases/ with:
           {"registration_id": <id>, "s3_key": "<key>", "file_name": "<name>"}

    The URL expires in 900 seconds (15 minutes). Max file size: 10 MB.

    ⚠️  Security note: the API trusts that the key refers to a file that
    was actually uploaded.  A production-grade system would issue a HEAD
    request to S3 to verify the object exists before accepting the key.
    """
    return storage.generate_upload_url(
        folder="releases/documents",
        filename=filename,
        content_type=content_type,
    )


@router.post("/", response_model=ReleaseRead, status_code=status.HTTP_201_CREATED)
def create_release(
    data: ReleaseCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_role("super_admin", "league_admin", "club_admin")
    ),
) -> PlayerRelease:
    # Club admins can only initiate releases for players in their own club
    if current_user.role == "club_admin":
        from app.models.registration import PlayerSeasonRegistration  # noqa: PLC0415

        reg = db.get(PlayerSeasonRegistration, data.registration_id)
        if reg is not None and reg.club_id != current_user.club_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Club admins can only initiate releases for their own club's players.",
            )
    release, error = release_service.create_release(db, data, current_user)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return release  # type: ignore[return-value]


@router.post("/{release_id}/decide/", response_model=ReleaseRead)
def decide_release(
    release_id: int,
    data: ReleaseDecide,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("player")),
) -> PlayerRelease:
    release = release_service.get_release_by_id(db, release_id)
    if release is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Release not found.")
    updated, error = release_service.decide_release(
        db, release, data.decision, current_user
    )
    if error:
        code = (
            status.HTTP_403_FORBIDDEN
            if "Only the" in error
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, error)
    return updated  # type: ignore[return-value]
