from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.release import ReleaseStatus


class ReleaseCreate(BaseModel):
    registration_id: int
    # placeholder until S3 upload is wired up
    file_url: str
    file_name: str
    effective_date: date | None = None


class ReleaseDecide(BaseModel):
    decision: Literal["confirm", "reject"]


class ReleaseDocumentRead(BaseModel):
    id: int
    release_id: int
    file_url: str
    file_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


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
