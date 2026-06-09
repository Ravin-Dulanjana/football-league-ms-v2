"""
Notification service.

Users see only their own notifications.  This is enforced at every query,
not just by FK — a user should never be able to see another user's notifications
even by guessing IDs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser
from app.models.notification import Notification, NotificationPreference
from app.schemas.notification import NotificationPreferenceUpdate


def get_notifications(db: Session, current_user: CurrentUser) -> list[Notification]:
    """Return the authenticated user's own notifications, newest first."""
    result = db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


def mark_read(
    db: Session, notification_id: int, current_user: CurrentUser
) -> tuple[Notification | None, str | None]:
    notif = db.get(Notification, notification_id)
    if notif is None:
        return None, "Notification not found."
    if notif.user_id != current_user.id:
        return None, "You can only mark your own notifications as read."
    notif.is_read = True
    notif.read_at = datetime.now(tz=UTC)
    db.commit()
    db.refresh(notif)
    return notif, None


def mark_all_read(db: Session, current_user: CurrentUser) -> int:
    """Mark all unread notifications as read.  Returns count updated."""
    unread = (
        db.execute(
            select(Notification).where(
                Notification.user_id == current_user.id,
                Notification.is_read.is_(False),
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(tz=UTC)
    for n in unread:
        n.is_read = True
        n.read_at = now
    db.commit()
    return len(unread)


def get_preferences(
    db: Session, current_user: CurrentUser
) -> list[NotificationPreference]:
    result = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    return list(result.scalars().all())


def upsert_preference(
    db: Session,
    event_type: str,
    data: NotificationPreferenceUpdate,
    current_user: CurrentUser,
) -> NotificationPreference:
    pref = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id,
            NotificationPreference.event_type == event_type,
        )
    ).scalar_one_or_none()

    if pref is None:
        pref = NotificationPreference(
            user_id=current_user.id,
            event_type=event_type,
            email_enabled=data.email_enabled,
            in_app_enabled=data.in_app_enabled,
        )
        db.add(pref)
    else:
        pref.email_enabled = data.email_enabled
        pref.in_app_enabled = data.in_app_enabled
        pref.updated_at = datetime.now(tz=UTC)

    db.commit()
    db.refresh(pref)
    return pref
