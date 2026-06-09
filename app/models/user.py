from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """
    PostgreSQL shadow record for a Cognito user.

    Cognito is the single source of truth for authentication (password,
    MFA, email verification). This table stores only what the application
    layer needs to reference users in FK relationships and to track
    when each user first authenticated.

    cognito_sub — the immutable UUID Cognito assigns to every user.
                  This is the stable link between Cognito and the DB.
    role        — mirrors custom:role from the Cognito ID token.
                  Updated on each request if the admin changed it in Cognito.
    club_id     — mirrors custom:club_id (club_admin users only).
    player_id   — mirrors custom:player_id (player users only).
    """

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_cognito_sub", "cognito_sub", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cognito_sub: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    # FK-like columns without FOREIGN KEY constraints so records can exist
    # before the linked club/player is created (admin accounts have neither).
    club_id: Mapped[int | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
