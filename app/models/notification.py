"""
Notification and NotificationPreference models.

Notification — one in-app notification per user event.  Users only ever
see their own notifications (enforced at query level, not via FK alone).

NotificationPreference — per-user, per-event-type opt-in/out settings.
Defaults to email=True, in_app=True if no preference row exists.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    # Human-readable message, e.g. "Season 2026 is now open for registration."
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPreference(Base):
    """
    Per-user, per-event-type preference.  One row per (user_id, event_type)
    pair.  Missing rows mean "use the default" (both channels enabled).
    """

    __tablename__ = "notification_preferences"
    __table_args__ = (
        Index(
            "uq_notif_pref_user_event",
            "user_id",
            "event_type",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
