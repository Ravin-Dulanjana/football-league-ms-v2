"""
Notification endpoints.

All endpoints are authenticated; each user sees only their own notifications.

GET  /notifications/                   — own notifications
POST /notifications/{id}/read/         — mark one read
POST /notifications/mark-all-read/     — mark all read
GET  /notifications/preferences/       — own preferences
PUT  /notifications/preferences/{event_type}/ — upsert preference
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user
from app.models.notification import Notification, NotificationPreference
from app.schemas.notification import (
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    NotificationRead,
)
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=list[NotificationRead])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Notification]:
    return notification_service.get_notifications(db, current_user)


@router.post("/{notification_id}/read/", response_model=NotificationRead)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Notification:
    notif, error = notification_service.mark_read(db, notification_id, current_user)
    if error:
        code = (
            status.HTTP_403_FORBIDDEN if "own" in error else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(code, error)
    return notif  # type: ignore[return-value]


@router.post("/mark-all-read/")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, int]:
    count = notification_service.mark_all_read(db, current_user)
    return {"marked_read": count}


@router.get("/preferences/", response_model=list[NotificationPreferenceRead])
def get_preferences(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[NotificationPreference]:
    return notification_service.get_preferences(db, current_user)


@router.put("/preferences/{event_type}/", response_model=NotificationPreferenceRead)
def upsert_preference(
    event_type: str,
    data: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationPreference:
    return notification_service.upsert_preference(db, event_type, data, current_user)
