"""
User management endpoints.

GET  /users/                       — super_admin and league_admin only
POST /users/                       — super_admin and league_admin only
PATCH /users/{id}/                 — super_admin only (stub)
DELETE /users/{id}/                — super_admin only (soft delete)
POST /users/{id}/account-action/   — super_admin and league_admin (scoped)
DELETE /users/{id}/hard-delete/    — super_admin only (permanent)
POST /users/{id}/restore/          — super_admin only
PATCH /users/{id}/role/            — super_admin only (assign/change governance role)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user
from app.dependencies.roles import (
    require_any_admin,
    require_league_admin_or_above,
    require_super_admin,
)
from app.models.user import User
from app.schemas.user import (
    AccountActionRequest,
    AssignRoleRequest,
    SoftDeleteRequest,
    UserCreate,
    UserRead,
)
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/", response_model=UserRead)
def get_me(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> User:
    """Return the currently authenticated user's own record (all roles)."""
    user = user_service.get_user_by_id(db, current_user.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    user_service.attach_governance_roles(db, [user])
    return user


@router.get("/{user_id}/", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_any_admin),
) -> User:
    """Any admin can fetch any user. Players/club-admins only see their own record."""
    if (
        current_user.role not in ("super_admin", "league_admin")
        and current_user.id != user_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied.")
    user = user_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    user_service.attach_governance_roles(db, [user])
    return user


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


@router.delete(
    "/{user_id}/hard-delete/",
    status_code=status.HTTP_204_NO_CONTENT,
)
def hard_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_super_admin),
) -> None:
    """
    Permanently delete a user record and their Cognito account.

    super_admin only. The user must already be soft-deleted (is_deleted=True).
    Two-step intentional process: soft-delete → review → hard delete.
    """
    target = user_service.get_user_by_id(db, user_id)
    if target is None:
        # Also check soft-deleted pool so super_admin can find them
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    ok, error = user_service.hard_delete_user(db, target, current_user)
    if not ok:
        code = (
            status.HTTP_400_BAD_REQUEST
            if error and "must be" in error.lower()
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(code, error)


@router.post("/{user_id}/restore/", response_model=UserRead)
def restore_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_super_admin),
) -> User:
    """
    Restore a soft-deleted user (super_admin only).

    Clears is_deleted, re-activates the account.
    Cognito password should be reset separately so the user can log in again.
    """
    # Must look up including deleted users — use a direct DB get (get_user_by_id
    # returns the row regardless of is_deleted since there is no filter on it).
    target = user_service.get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    restored, error = user_service.restore_user(db, target, current_user)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return restored  # type: ignore[return-value]


@router.patch("/{user_id}/role/", response_model=UserRead)
def assign_role(
    user_id: int,
    body: AssignRoleRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_super_admin),
) -> User:
    """
    Assign or change a user's governance role (super_admin only).

    The user's member_type (player/club_staff) is preserved — this action only
    changes the governance/access role, not the person's fundamental identity.

    Example use cases:
      - Player elected club president → assign club_admin (member_type stays "player")
      - Club admin steps down → assign player or club_staff
      - Player appointed league official → assign league_admin
    """
    target = user_service.get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    updated, error = user_service.assign_role(
        db, target, body.new_role, body.club_id, body.reason, current_user
    )
    if error:
        code = (
            status.HTTP_403_FORBIDDEN
            if "cannot" in error.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, error)
    return updated  # type: ignore[return-value]
