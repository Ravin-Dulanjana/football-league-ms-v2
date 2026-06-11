import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SeasonStatus(enum.StrEnum):
    DRAFT = "draft"
    OPEN = "open"  # registration window open
    ACTIVE = "active"  # season running — roster locked
    CLOSED = "closed"  # season ended
    ARCHIVED = "archived"


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("year", name="unique_year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    year: Mapped[int] = mapped_column(Integer)
    registration_open_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    registration_close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    season_end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def status(self) -> SeasonStatus:
        if self.is_archived:
            return SeasonStatus.ARCHIVED
        now = datetime.now(tz=UTC)
        reg_open = self.registration_open_at
        # SQLite returns naive datetimes; normalise to avoid comparison errors.
        if reg_open.tzinfo is None:
            now = now.replace(tzinfo=None)
        if now < reg_open:
            return SeasonStatus.DRAFT
        if now <= self.registration_close_at:
            return SeasonStatus.OPEN
        if self.season_end_date is None or now <= self.season_end_date:
            return SeasonStatus.ACTIVE
        return SeasonStatus.CLOSED

    @property
    def is_locked(self) -> bool:
        return self.status == SeasonStatus.ACTIVE
