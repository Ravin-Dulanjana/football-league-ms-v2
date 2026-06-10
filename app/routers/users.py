"""
User management endpoints.

GET  /users/                  — super_admin and league_admin only
POST /users/                  — super_admin and league_admin only
PATCH /users/{id}/            — super_admin only
DELETE /users/{id}/           — super_admin only (soft delete)
POST /users/{id}/account-action/ — super_admin and league_admin (scoped)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser
from app.dependencies.roles import (
    require_any_admin,
    require_league_admin_or_above,
)
from app.models.user import User
from app.schemas.user import (
    AccountActionRequest,
    SoftDeleteRequest,
    UserCreate,
    UserRead,
)
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserRead])
def list_users(
    include_deleted: bool = Query(False, alias="include_deleted"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_league_admin_or_above),
) -> list[User]:
    """
    super_admin sees all users; with ?include_deleted=1 also sees soft-deleted.
    league_admin sees all non-deleted users.
    """
    return user_service.get_all_users(db, current_user, include_deleted)


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_any_admin),
) -> User:
    user, error = user_service.create_user(db, data, current_user)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return user  # type: ignore[return-value]


@router.patch("/{user_id}/", response_model=UserRead)
def update_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_league_admin_or_above),
) -> User:
    """
    General update is super_admin only.
    league_admin gets 403 with a message directing them to account-action.
    """
    if current_user.role != "super_admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Use dedicated recovery actions for account updates. "
            "League admins cannot directly update user records.",
        )
    # Stub — add update logic (email/role change) in future iterations
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED, "User record updates not yet implemented."
    )


@router.delete("/{user_id}/", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user(
    user_id: int,
    body: SoftDeleteRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_league_admin_or_above),
) -> None:
    target = user_service.get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    _, error = user_service.soft_delete_user(db, target, current_user, body.reason)
    if error:
        code = (
            status.HTTP_403_FORBIDDEN
            if "cannot" in error.lower() or "only" in error.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, error)


@router.post("/{user_id}/account-action/", response_model=UserRead)
def account_action(
    user_id: int,
    body: AccountActionRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_league_admin_or_above),
) -> User:
    target = user_service.get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    updated, error = user_service.perform_account_action(db, target, body, current_user)
    if error:
        code = (
            status.HTTP_403_FORBIDDEN
            if "cannot" in error.lower() or "league admin" in error.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, error)
    return updated  # type: ignore[return-value]
