"""Pydantic schemas for league info endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, computed_field

from app.services import storage


class LeagueInfoRead(BaseModel):
    id: int
    league_name: str
    founded_year: int | None
    president_name: str | None
    secretary_name: str | None
    treasurer_name: str | None
    email: str | None
    phone_number: str | None
    logo_key: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def logo_url(self) -> str | None:
        if not self.logo_key:
            return None
        return storage.get_file_url(self.logo_key)


class LeagueInfoUpdate(BaseModel):
    league_name: str | None = None
    founded_year: int | None = None
    president_name: str | None = None
    secretary_name: str | None = None
    treasurer_name: str | None = None
    email: str | None = None
    phone_number: str | None = None
    logo_key: str | None = None
