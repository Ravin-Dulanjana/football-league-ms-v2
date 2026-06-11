from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.season import SeasonStatus


class SeasonRead(BaseModel):
    id: int
    name: str
    year: int
    registration_open_at: datetime
    registration_close_at: datetime
    season_end_date: datetime | None
    is_locked: bool
    is_archived: bool
    status: SeasonStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class SeasonCreate(BaseModel):
    name: str
    year: int
    registration_open_at: datetime
    registration_close_at: datetime
    season_end_date: datetime | None = None

    @model_validator(mode="after")
    def check_date_order(self) -> SeasonCreate:
        if self.registration_close_at <= self.registration_open_at:
            raise ValueError("registration_close_at must be after registration_open_at")
        if self.season_end_date and self.season_end_date <= self.registration_close_at:
            raise ValueError("season_end_date must be after registration_close_at")
        return self


class SeasonUpdate(BaseModel):
    name: str | None = None
    registration_open_at: datetime | None = None
    registration_close_at: datetime | None = None
    season_end_date: datetime | None = None
    is_archived: bool | None = None
