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
    is_locked: bool
    status: SeasonStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class SeasonCreate(BaseModel):
    name: str
    year: int
    registration_open_at: datetime
    registration_close_at: datetime

    @model_validator(mode="after")
    def check_window_order(self) -> SeasonCreate:
        if self.registration_close_at <= self.registration_open_at:
            raise ValueError("registration_close_at must be after registration_open_at")
        return self


class SeasonUpdate(BaseModel):
    name: str | None = None
    registration_open_at: datetime | None = None
    registration_close_at: datetime | None = None
    is_locked: bool | None = None
    status: SeasonStatus | None = None
