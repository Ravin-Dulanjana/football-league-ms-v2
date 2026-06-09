"""
Audit log helper.

Every significant write operation calls write_audit_log().  The audit log
is append-only — rows are never updated or deleted.

Usage:
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="user.deactivate",
        entity_type="User",
        entity_id=target_user.id,
        details={"reason": "policy violation"},
    )
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit_log(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: dict | None = None,
) -> AuditLog:
    """
    Insert one audit log row and flush (but do not commit).

    The caller is responsible for the final db.commit() so the audit row
    lands in the same transaction as the change it describes.  If the
    transaction rolls back, the audit row is also rolled back — consistent.
    """
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details) if details else None,
    )
    db.add(log)
    db.flush()  # assign an ID without committing
    return log


def get_audit_logs(
    db: Session,
    *,
    action: str | None = None,
    actor_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Return filtered audit log rows, newest first."""
    q = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        q = q.where(AuditLog.action == action)
    if actor_id is not None:
        q = q.where(AuditLog.actor_id == actor_id)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(AuditLog.entity_id == entity_id)
    return list(db.execute(q.offset(offset).limit(limit)).scalars().all())
