"""
LeagueInfo — singleton row (id=1) storing league-wide metadata.

Only league_admin and super_admin may update this.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.player import Player

from app.models.base import Base


class LeagueInfo(Base):
    __tablename__ = "league_info"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    president_name: Mapped[str | None] = mapped_column(String(128))
    secretary_name: Mapped[str | None] = mapped_column(String(128))
    treasurer_name: Mapped[str | None] = mapped_column(String(128))
    president_player_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    secretary_player_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    treasurer_player_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    president: Mapped[Player | None] = relationship(
        "Player", foreign_keys=[president_player_id], lazy="select"
    )
    secretary: Mapped[Player | None] = relationship(
        "Player", foreign_keys=[secretary_player_id], lazy="select"
    )
    treasurer: Mapped[Player | None] = relationship(
        "Player", foreign_keys=[treasurer_player_id], lazy="select"
    )
    email: Mapped[str | None] = mapped_column(String(255))
    phone_number: Mapped[str | None] = mapped_column(String(32))
    logo_key: Mapped[str | None] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
