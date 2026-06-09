from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, computed_field

from app.config import settings
from app.models.player import PlayerStatus


class PlayerRead(BaseModel):
    id: int
    league_player_code: str
    full_name: str
    date_of_birth: date
    nic_number: str
    # photo_key is the raw S3 object key stored in the database.
    # photo_url is computed from it — not stored, built at serialisation time.
    photo_key: str | None
    status: PlayerStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def photo_url(self) -> str | None:
        """
        Build the CloudFront URL from the stored S3 object key.

        Returns None if no photo has been uploaded.
        Returns the raw key if CLOUDFRONT_DOMAIN is not configured.
        """
        if not self.photo_key:
            return None
        if not settings.cloudfront_domain:
            return self.photo_key
        return f"https://{settings.cloudfront_domain}/{self.photo_key}"


class PlayerCreate(BaseModel):
    full_name: str
    date_of_birth: date
    nic_number: str
    # photo_key is optional on creation — the photo upload is a separate step.
    photo_key: str | None = None


class PlayerUpdate(BaseModel):
    # nic_number and date_of_birth are intentionally excluded — immutable once set
    full_name: str | None = None
    # Set this to the S3 key returned by the photo upload URL endpoint.
    photo_key: str | None = None
    status: PlayerStatus | None = None
