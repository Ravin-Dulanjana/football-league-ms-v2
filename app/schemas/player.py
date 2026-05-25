from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from app.models.player import PlayerStatus


class PlayerRead(BaseModel):
    id: int
    league_player_code: str
    full_name: str
    date_of_birth: date
    nic_number: str
    photo_url: str | None
    status: PlayerStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlayerCreate(BaseModel):
    full_name: str
    date_of_birth: date
    nic_number: str
    photo_url: str | None = None


class PlayerUpdate(BaseModel):
    # nic_number and date_of_birth are intentionally excluded — immutable once set
    full_name: str | None = None
    photo_url: str | None = None
    status: PlayerStatus | None = None
