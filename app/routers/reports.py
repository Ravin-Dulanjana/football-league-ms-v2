"""
Reporting and analytics endpoints.

GET /reports/export/    — any admin role, returns CSV (or 501 for pdf)
GET /analytics/summary/ — any admin role, returns JSON summary
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser
from app.dependencies.roles import require_any_admin
from app.services import report_service

router = APIRouter(tags=["reports"])

_VALID_REPORT_TYPES = {"season_rosters", "release_history", "club_staff"}


@router.get("/reports/export/", response_class=PlainTextResponse)
def export_report(
    report_type: str = Query(
        ..., description="season_rosters|release_history|club_staff"
    ),  # noqa: E501
    file_format: str = Query("csv", description="csv or pdf (pdf returns 501)"),
    season_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_any_admin),
) -> str:
    if file_format == "pdf":
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "PDF export is not yet implemented. "
            "Use file_format=csv or request PDF support in a future release. "
            "# TODO: integrate reportlab or weasyprint",
        )
    if report_type not in _VALID_REPORT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid report_type. Must be one of: {', '.join(_VALID_REPORT_TYPES)}",
        )
    return report_service.export_csv(db, report_type, current_user, season_id)


@router.get("/analytics/summary/")
def analytics_summary(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_any_admin),
) -> dict:
    return report_service.get_analytics_summary(db, current_user)
