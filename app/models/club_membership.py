from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ClubMembershipRequestStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ClubMembershipRequest(Base):
    """
    A club admin invites a free player (or club_staff) to join their club.

    Flow:
      1. club_admin POST /club-membership-requests/ with player_id
      2. Player sees the pending invite and calls POST /…/{id}/decide/
         with decision="accept" or "reject"
      3. On accept: player.club_id is set to the club's id
      4. On reject/cancel: no change to player.club_id

    A player can only have ONE active club at a time.  Creating an invite is
    only allowed when player.club_id IS NULL (free player).  To move clubs,
    the current club must first release the player.
    """

    __tablename__ = "club_membership_requests"
    __table_args__ = (
        Index("ix_cmr_player_status", "player_id", "status"),
        Index("ix_cmr_club_status", "club_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    club_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ClubMembershipRequestStatus.PENDING,
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped[Player] = relationship("Player")
    club: Mapped[Club] = relationship("Club")


from app.models.club import Club  # noqa: E402
from app.models.player import Player  # noqa: E402
