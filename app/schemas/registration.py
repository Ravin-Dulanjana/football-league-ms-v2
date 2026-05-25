from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.registration import (
    PlayerSeasonRegistrationStatus,
    RegistrationRequestStatus,
    RegistrationType,
)


class RegistrationRequestCreate(BaseModel):
    player_id: int
    club_id: int
    season_id: int


class RegistrationRequestRead(BaseModel):
    id: int
    season_id: int
    club_id: int
    player_id: int
    status: RegistrationRequestStatus
    responded_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RegistrationDecide(BaseModel):
    decision: Literal["accept", "reject"]


class PlayerSeasonRegistrationRead(BaseModel):
    id: int
    season_id: int
    club_id: int
    player_id: int
    registration_type: RegistrationType
    status: PlayerSeasonRegistrationStatus
    registered_at: datetime
    released_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
