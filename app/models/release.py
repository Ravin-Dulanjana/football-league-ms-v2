from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ReleaseStatus(enum.StrEnum):
    PENDING_PLAYER_CONFIRMATION = "pending_player_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PlayerRelease(Base):
    __tablename__ = "player_releases"
    __table_args__ = (
        Index("ix_releases_from_club_status", "from_club_id", "status"),
        Index("ix_releases_player_status", "player_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Optional: only set for releases that were tied to a season registration.
    # New-style direct releases (club removes player mid-membership) leave this null.
    registration_id: Mapped[int | None] = mapped_column(
        ForeignKey("player_season_registrations.id", ondelete="SET NULL"),
    )
    # denormalised for query convenience (avoid joining through registration)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    from_club_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE")
    )
    status: Mapped[ReleaseStatus] = mapped_column(
        Enum(
            ReleaseStatus,
            name="releasestatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ReleaseStatus.CONFIRMED,
    )
    effective_date: Mapped[date | None] = mapped_column(Date)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    registration: Mapped[PlayerSeasonRegistration | None] = relationship(
        "PlayerSeasonRegistration", back_populates="release"
    )
    player: Mapped[Player] = relationship("Player")
    from_club: Mapped[Club] = relationship("Club")
    documents: Mapped[list[ReleaseDocument]] = relationship(
        "ReleaseDocument", back_populates="release", cascade="all, delete-orphan"
    )


class ReleaseDocument(Base):
    __tablename__ = "release_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(
        ForeignKey("player_releases.id", ondelete="CASCADE")
    )
    # S3 object key for this document (e.g. "releases/documents/uuid.pdf").
    s3_key: Mapped[str] = mapped_column(String(512))
    file_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    release: Mapped[PlayerRelease] = relationship(
        "PlayerRelease", back_populates="documents"
    )


class PlayerDocument(Base):
    """Player-uploaded external release documents (e.g. from other leagues/clubs)."""

    __tablename__ = "player_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    s3_key: Mapped[str] = mapped_column(String(512))
    file_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped[Player] = relationship("Player")


# avoid circular imports at module level
from app.models.club import Club  # noqa: E402
from app.models.player import Player  # noqa: E402
from app.models.registration import PlayerSeasonRegistration  # noqa: E402
