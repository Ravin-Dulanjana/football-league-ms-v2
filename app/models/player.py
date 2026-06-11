import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, func
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
    # Stores the S3 object key (e.g. "players/photos/uuid.jpg"), not a URL.
    # The CloudFront URL is built at read time by get_file_url() in storage.py.
    photo_key: Mapped[str | None] = mapped_column(String(512))
    # Current club membership — null means the player is free (not in any club).
    # Set when a ClubMembershipRequest is accepted; cleared when released.
    club_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("clubs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
