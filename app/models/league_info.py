"""
LeagueInfo — singleton row (id=1) storing league-wide metadata.

Only league_admin and super_admin may update this.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LeagueInfo(Base):
    __tablename__ = "league_info"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    president_name: Mapped[str | None] = mapped_column(String(128))
    secretary_name: Mapped[str | None] = mapped_column(String(128))
    treasurer_name: Mapped[str | None] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(255))
    phone_number: Mapped[str | None] = mapped_column(String(32))
    logo_key: Mapped[str | None] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
