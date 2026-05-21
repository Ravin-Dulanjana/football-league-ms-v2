import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.league import League


class SeasonStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("league_id", "year", name="unique_league_year"),
        Index("ix_seasons_league_status", "league_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    year: Mapped[int] = mapped_column(Integer)
    registration_open_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    registration_close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_locked: Mapped[bool] = mapped_column(default=False)
    status: Mapped[SeasonStatus] = mapped_column(
        Enum(SeasonStatus, name="seasonstatus"), default=SeasonStatus.DRAFT
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    league: Mapped["League"] = relationship("League", back_populates="seasons")
