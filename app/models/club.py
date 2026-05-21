import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.league import League


class ClubStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Club(Base):
    __tablename__ = "clubs"
    __table_args__ = (
        UniqueConstraint("league_id", "name", name="unique_club_name_in_league"),
        UniqueConstraint("league_id", "code", name="unique_club_code_in_league"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    short_name: Mapped[Optional[str]] = mapped_column(String(32))
    code: Mapped[str] = mapped_column(String(32))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    logo_url: Mapped[Optional[str]] = mapped_column(String(512))
    status: Mapped[ClubStatus] = mapped_column(
        Enum(ClubStatus, name="clubstatus"), default=ClubStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    league: Mapped["League"] = relationship("League", back_populates="clubs")
