"""
AuditLog — immutable record of every significant write operation.

Every action that mutates user accounts, season state, club season profiles,
or unlock requests writes one row here.  Rows are NEVER updated or deleted —
the audit trail must be append-only.

Fields:
  actor_id    — the User.id who performed the action (None for system events)
  action      — short string key, e.g. "user.deactivate", "season.status_change"
  entity_type — the name of the resource being changed, e.g. "User", "Season"
  entity_id   — the integer PK of the changed resource
  details     — JSON blob with before/after values or reason text
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # actor_id is nullable: system-generated events (e.g. auto-expiry) have None
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Free-form JSON stored as text — keeps the schema simple and avoids
    # a dependency on a JSON column type across SQLite (tests) and Postgres.
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
