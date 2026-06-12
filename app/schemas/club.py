from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, computed_field

from app.models.club import ClubStatus
from app.services import storage


class ClubRead(BaseModel):
    id: int
    name: str
    short_name: str | None
    code: str
    email: str | None
    phone_number: str | None
    # logo_key is the raw S3 object key stored in the database.
    # logo_url is computed from it — not stored, built at serialisation time.
    logo_key: str | None
    status: ClubStatus
    established_year: int | None
    president_name: str | None
    secretary_name: str | None
    treasurer_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def logo_url(self) -> str | None:
        """
        Build the public URL from the stored S3 object key via storage.get_file_url.

        Returns None if no logo has been uploaded.
        Falls back to a direct S3 URL when CLOUDFRONT_DOMAIN is not configured.
        """
        if not self.logo_key:
            return None
        return storage.get_file_url(self.logo_key)


class ClubCreate(BaseModel):
    name: str
    short_name: str | None = None
    code: str
    email: str | None = None
    phone_number: str | None = None
    established_year: int | None = None
    president_name: str | None = None
    secretary_name: str | None = None
    treasurer_name: str | None = None
    # logo_key is optional on creation — the logo upload is a separate step.
    # Flow: create club → get upload URL → upload to S3 → PATCH with logo_key.
    logo_key: str | None = None


class ClubUpdate(BaseModel):
    name: str | None = None
    short_name: str | None = None
    code: str | None = None
    email: str | None = None
    phone_number: str | None = None
    # Set this to the S3 key returned by the logo upload URL endpoint.
    logo_key: str | None = None
    status: ClubStatus | None = None
    established_year: int | None = None
    president_name: str | None = None
    secretary_name: str | None = None
    treasurer_name: str | None = None


class UploadUrlResponse(BaseModel):
    """
    Returned by all *-upload-url endpoints.

    url:      POST this URL directly to S3 (not to the API).
    fields:   Include all of these as form fields in the multipart POST,
              in the order they appear, BEFORE the file field.
              boto3's presigned POST requires this ordering.
    key:      The S3 object key that will be created on upload.
              After a successful upload, send this key back to the API
              (e.g. PATCH /clubs/{id}/ with {"logo_key": "<key>"}).
    expires_in: Seconds until the upload URL expires (900 = 15 minutes).
    """

    url: str
    fields: dict[str, str]
    key: str
    expires_in: int
