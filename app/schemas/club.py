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


class ClubCreate(BaseModel):
    name: str
    short_name: str | None = None
    code: str
    email: str | None = None
    logo_url: str | None = None


class ClubUpdate(BaseModel):
    name: str | None = None
    short_name: str | None = None
    code: str | None = None
    email: str | None = None
    logo_url: str | None = None
    status: ClubStatus | None = None
