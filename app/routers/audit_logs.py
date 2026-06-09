"""
Audit log endpoints.

GET /audit-logs/        — super_admin and league_admin only
GET /audit-logs/export/ — same scoping, CSV, max 10 000 rows
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser
from app.dependencies.roles import require_league_admin_or_above
from app.models.audit_log import AuditLog
from app.schemas.notification import AuditLogRead
from app.services import audit_service

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("/", response_model=list[AuditLogRead])
def list_audit_logs(
    action: str | None = Query(None),
    actor_id: int | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: int | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_league_admin_or_above),
) -> list[AuditLog]:
    return audit_service.get_audit_logs(
        db,
        action=action,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )


@router.get("/export/", response_class=PlainTextResponse)
def export_audit_logs(
    action: str | None = Query(None),
    actor_id: int | None = Query(None),
    entity_type: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_league_admin_or_above),
) -> str:
    """Return up to 10 000 rows as a CSV file."""
    import csv  # noqa: PLC0415
    import io  # noqa: PLC0415

    rows = audit_service.get_audit_logs(
        db,
        action=action,
        actor_id=actor_id,
        entity_type=entity_type,
        limit=10000,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "actor_id",
            "action",
            "entity_type",
            "entity_id",
            "details",
            "created_at",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.actor_id,
                row.action,
                row.entity_type,
                row.entity_id,
                row.details or "",
                row.created_at.isoformat(),
            ]
        )
    return buf.getvalue()
