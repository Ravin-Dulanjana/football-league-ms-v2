import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlayerStatus(enum.StrEnum):
    PENDING_CLAIM = "pending_claim"
    ACTIVE = "active"
    INACTIVE = "inactive"


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_player_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    date_of_birth: Mapped[date] = mapped_column(Date)
    nic_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    photo_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[PlayerStatus] = mapped_column(
        Enum(
            PlayerStatus,
            name="playerstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=PlayerStatus.PENDING_CLAIM,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
