from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RegistrationRequestStatus(enum.StrEnum):
    PENDING_PLAYER_CONFIRMATION = "pending_player_confirmation"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class RegistrationType(enum.StrEnum):
    NEW = "new"
    RENEWAL = "renewal"
    TRANSFER = "transfer"


class PlayerSeasonRegistrationStatus(enum.StrEnum):
    ACTIVE = "active"
    RELEASED = "released"
    CANCELLED = "cancelled"


class RegistrationRequest(Base):
    __tablename__ = "registration_requests"
    __table_args__ = (
        Index("ix_reg_requests_season_club_status", "season_id", "club_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"))
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    requested_by_user_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[RegistrationRequestStatus] = mapped_column(
        Enum(
            RegistrationRequestStatus,
            name="registrationrequeststatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION,
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    season: Mapped[Season] = relationship("Season")
    club: Mapped[Club] = relationship("Club")
    player: Mapped[Player] = relationship("Player")


class PlayerSeasonRegistration(Base):
    __tablename__ = "player_season_registrations"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "season_id", name="uq_player_season_registration"
        ),
        Index("ix_psr_club_season_status", "club_id", "season_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"))
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    registration_type: Mapped[RegistrationType] = mapped_column(
        Enum(
            RegistrationType,
            name="registrationtype",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=RegistrationType.NEW,
    )
    status: Mapped[PlayerSeasonRegistrationStatus] = mapped_column(
        Enum(
            PlayerSeasonRegistrationStatus,
            name="playerseasonregistrationstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=PlayerSeasonRegistrationStatus.ACTIVE,
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    season: Mapped[Season] = relationship("Season")
    club: Mapped[Club] = relationship("Club")
    player: Mapped[Player] = relationship("Player")
    release: Mapped[PlayerRelease | None] = relationship(
        "PlayerRelease", back_populates="registration", uselist=False
    )


# avoid circular imports at module level — only needed for type resolution
from app.models.club import Club  # noqa: E402
from app.models.player import Player  # noqa: E402
from app.models.release import PlayerRelease  # noqa: E402
from app.models.season import Season  # noqa: E402
