from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, computed_field

from app.config import settings
from app.models.release import ReleaseStatus


class ReleaseCreate(BaseModel):
    registration_id: int
    # s3_key: the S3 object key returned by POST /releases/document-upload-url/
    # The file must be uploaded to S3 BEFORE calling this endpoint.
    # ⚠️  The API trusts that the key refers to an object that was actually
    #     uploaded.  A production system would verify this with a HEAD request
    #     to S3 before accepting the key.
    s3_key: str
    # file_name: the original filename shown to the player and club admin.
    # Used for display only — not the S3 key, not a filesystem path.
    file_name: str
    effective_date: date | None = None


class ReleaseDecide(BaseModel):
    decision: Literal["confirm", "reject"]


class ReleaseDocumentRead(BaseModel):
    id: int
    release_id: int
    # s3_key is the raw S3 object key stored in the database.
    # file_url is computed from it — the CloudFront URL for serving the file.
    s3_key: str
    file_name: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def file_url(self) -> str:
        """
        Build the CloudFront URL from the stored S3 object key.

        Returns the raw key if CLOUDFRONT_DOMAIN is not configured.
        """
        if not settings.cloudfront_domain:
            return self.s3_key
        return f"https://{settings.cloudfront_domain}/{self.s3_key}"


class ReleaseRead(BaseModel):
    id: int
    registration_id: int
    player_id: int
    from_club_id: int
    status: ReleaseStatus
    effective_date: date | None
    confirmed_at: datetime | None
    created_at: datetime
    documents: list[ReleaseDocumentRead]

    model_config = {"from_attributes": True}
