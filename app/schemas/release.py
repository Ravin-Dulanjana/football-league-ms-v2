from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, computed_field

from app.config import settings
from app.models.release import ReleaseStatus


class ReleaseCreate(BaseModel):
    # Target player — club must own this player (player.club_id == caller's club)
    player_id: int
    # s3_key: the S3 object key returned by POST /releases/document-upload-url/
    # The file must be uploaded to S3 BEFORE calling this endpoint.
    s3_key: str
    file_name: str
    effective_date: date | None = None


class ReleaseDecide(BaseModel):
    decision: Literal["confirm"]


class ReleaseDocumentRead(BaseModel):
    id: int
    release_id: int
    s3_key: str
    file_name: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def file_url(self) -> str:
        if not settings.cloudfront_domain:
            return self.s3_key
        return f"https://{settings.cloudfront_domain}/{self.s3_key}"


class ReleaseRead(BaseModel):
    id: int
    registration_id: int | None
    player_id: int
    from_club_id: int
    status: ReleaseStatus
    effective_date: date | None
    confirmed_at: datetime | None
    created_at: datetime
    documents: list[ReleaseDocumentRead]

    model_config = {"from_attributes": True}


class PlayerDocumentCreate(BaseModel):
    s3_key: str
    file_name: str
    year: int | None = None
    league_name: str | None = None
    club_name: str | None = None
    description: str | None = None


class PlayerDocumentRead(BaseModel):
    id: int
    player_id: int
    s3_key: str
    file_name: str
    description: str | None
    year: int | None
    league_name: str | None
    club_name: str | None
    is_visible: bool
    source: str
    release_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def file_url(self) -> str:
        if not settings.cloudfront_domain:
            return self.s3_key
        domain = settings.cloudfront_domain.removeprefix("https://")
        return f"https://{domain}/{self.s3_key}"
