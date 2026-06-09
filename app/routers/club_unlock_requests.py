"""
ClubUnlockRequest endpoints.

GET  /club-unlock-requests/           — scoped by role
POST /club-unlock-requests/           — club_admin for their club or league_admin
POST /club-unlock-requests/{id}/decide/ — league_admin or super_admin only
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user
from app.dependencies.roles import require_league_admin_or_above
from app.models.club_season import ClubUnlockRequest, UnlockApproval
from app.schemas.club_season import (
    UnlockRequestCreate,
    UnlockRequestDecide,
    UnlockRequestRead,
)
from app.services import club_season_service
from app.services.role_checks import can_manage_club


class _UnlockRequestReadWithCount(UnlockRequestRead):
    pass


router = APIRouter(prefix="/club-unlock-requests", tags=["club-unlock-requests"])


def _to_read(req: ClubUnlockRequest, db: Session) -> dict:
    from sqlalchemy import func, select  # noqa: PLC0415

    count = db.execute(
        select(func.count()).where(UnlockApproval.request_id == req.id)
    ).scalar_one()
    return {
        "id": req.id,
        "club_id": req.club_id,
        "season_id": req.season_id,
        "reason": req.reason,
        "status": req.status,
        "approval_count": count,
        "created_at": req.created_at,
        "decided_at": req.decided_at,
    }


@router.get("/", response_model=list[UnlockRequestRead])
def list_requests(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    reqs = club_season_service.get_unlock_requests(db, current_user)
    return [_to_read(r, db) for r in reqs]


@router.post("/", response_model=UnlockRequestRead, status_code=status.HTTP_201_CREATED)
def create_request(
    data: UnlockRequestCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    # Must be club_admin for their own club OR league_admin/super_admin
    if not can_manage_club(current_user, data.club_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You cannot create an unlock request for this club.",
        )
    req, error = club_season_service.create_unlock_request(db, data, current_user)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return _to_read(req, db)  # type: ignore[arg-type]


@router.post("/{request_id}/decide/", response_model=UnlockRequestRead)
def decide_request(
    request_id: int,
    data: UnlockRequestDecide,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_league_admin_or_above),
) -> dict:
    req = club_season_service.get_unlock_request_by_id(db, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unlock request not found.")

    updated, error = club_season_service.decide_unlock_request(
        db, req, data.decision, current_user
    )
    if error:
        code = (
            status.HTTP_403_FORBIDDEN
            if "cannot" in error.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, error)
    return _to_read(updated, db)  # type: ignore[arg-type]
