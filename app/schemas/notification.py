"""Pydantic schemas for Notification and NotificationPreference."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: int
    event_type: str
    message: str
    is_read: bool
    created_at: datetime
    read_at: datetime | None

    model_config = {"from_attributes": True}


class NotificationPreferenceRead(BaseModel):
    event_type: str
    email_enabled: bool
    in_app_enabled: bool

    model_config = {"from_attributes": True}


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool
    in_app_enabled: bool


class AuditLogRead(BaseModel):
    id: int
    actor_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    details: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
