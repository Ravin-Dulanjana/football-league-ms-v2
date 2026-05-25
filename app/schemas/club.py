from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.club import ClubStatus


class ClubRead(BaseModel):
    id: int
    name: str
    short_name: str | None
    code: str
    email: str | None
    logo_url: str | None
    status: ClubStatus
    created_at: datetime

    model_config = {"from_attributes": True}
