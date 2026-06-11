import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SeasonStatus(enum.StrEnum):
    DRAFT = "draft"
    OPEN = "open"  # registration window is open
    ACTIVE = "active"  # season running — roster locked
    CLOSED = "closed"  # season ended — releases / new invites allowed
    ARCHIVED = "archived"


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("year", name="unique_year"),
        Index("ix_seasons_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    year: Mapped[int] = mapped_column(Integer)
    registration_open_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    registration_close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    season_end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # is_locked is auto-managed: True when status == ACTIVE, False otherwise.
    is_locked: Mapped[bool] = mapped_column(default=False)
    status: Mapped[SeasonStatus] = mapped_column(
        Enum(
            SeasonStatus,
            name="seasonstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=SeasonStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
