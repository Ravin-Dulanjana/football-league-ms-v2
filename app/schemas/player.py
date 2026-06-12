from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, computed_field

from app.models.player import PlayerStatus
from app.services import storage


class PlayerRead(BaseModel):
    id: int
    league_player_code: str
    full_name: str
    date_of_birth: date
    nic_number: str
    photo_key: str | None
    club_id: int | None
    status: PlayerStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def photo_url(self) -> str | None:
        """
        Build the public URL from the stored S3 object key via storage.get_file_url.

        Returns None if no photo has been uploaded.
        Falls back to a direct S3 URL when CLOUDFRONT_DOMAIN is not configured.
        """
        if not self.photo_key:
            return None
        return storage.get_file_url(self.photo_key)


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
