from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """
    PostgreSQL shadow record for a Cognito user.

    Cognito is the single source of truth for authentication (password,
    MFA, email verification).  This table stores only what the application
    layer needs to reference users in FK relationships, enforce soft-delete,
    and track account lifecycle.

    cognito_sub           — the immutable UUID Cognito assigns to every user.
    role                  — mirrors custom:role from the Cognito ID token.
                            Updated on each request if the admin changed it.
    club_id               — mirrors custom:club_id (club_admin only).
    player_id             — mirrors custom:player_id (player only).
    is_active             — False means the account is deactivated.
    is_deleted            — soft-delete flag; set True instead of DELETE.
    deleted_at            — timestamp of soft-delete.
    deleted_by            — User.id who performed the soft-delete.
    force_password_change — True after admin-triggered password reset.
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
    # ------------------------------------------------------------------
    # Phase 8 — account lifecycle fields
    # ------------------------------------------------------------------
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true"
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Self-referential; stored as plain int to avoid circular FK issues.
    deleted_by: Mapped[int | None] = mapped_column(nullable=True)
    # True after an admin resets the password via the account-action endpoint.
    # The login flow should check this flag and force a password change UI.
    force_password_change: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    # Informational; updated by user_sync on each successful token verification.
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
