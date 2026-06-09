"""
Reusable FastAPI permission dependencies for role-based access control.

These functions are passed to route handlers via FastAPI's Depends() mechanism.
They run before the route handler, so a 403 or 401 short-circuits before any
service code is reached.

Why here and not in services?
  Services are pure business logic.  Dependencies live at the HTTP boundary —
  they know about HTTPException, Request, path parameters, and headers.
  Keeping them separate means service functions stay testable with plain calls.

Usage:
    from app.dependencies.roles import require_super_admin, require_club_manager

    @router.post("/seasons/")
    def create_season(
        data: SeasonCreate,
        db: Session = Depends(get_db),
        _: CurrentUser = Depends(require_super_admin),
    ): ...

    @router.patch("/clubs/{club_id}/")
    def update_club(
        club_id: int,
        data: ClubUpdate,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(require_club_manager),
    ): ...
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.dependencies import CurrentUser, get_current_user
from app.services import role_checks


def require_authenticated(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Require any authenticated user.

    get_current_user already raises 401 when no token is present, so this is
    effectively an alias — useful for explicit documentation of public-vs-auth
    intent in route signatures.
    """
    return current_user


def require_super_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Require the super_admin role.

    super_admin accounts are created manually (no self-registration).  They
    have unrestricted access to every endpoint.
    """
    if not role_checks.is_super_admin(current_user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Access denied. This endpoint requires the super_admin role.",
        )
    return current_user


def require_league_admin_or_above(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Require league_admin or super_admin role.

    Used for league-level management actions: creating seasons, approving
    club season profiles, viewing audit logs, managing users, etc.
    """
    if not (
        role_checks.is_super_admin(current_user)
        or role_checks.is_league_admin(current_user)
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Access denied. This endpoint requires the league_admin or "
            "super_admin role.",
        )
    return current_user


def require_any_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Require any administrative role (super_admin, league_admin, or club_admin).

    Used for write endpoints that all admins can reach, but whose scope differs
    per role (e.g. reports, analytics, registration requests).
    """
    if not role_checks.has_any_admin_role(current_user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Access denied. This endpoint requires an admin role.",
        )
    return current_user


def require_club_manager(
    club_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Require the ability to manage a specific club.

    Passes for: super_admin (all clubs), league_admin (all clubs in the league),
    club_admin whose account is linked to this specific club_id.

    The club_id is resolved from the URL path parameter automatically by
    FastAPI — the route must include /{club_id}/ in its path.

    Raises 403 (not 404) so that club_admin users cannot enumerate clubs by
    trying different IDs and observing whether they get 403 or 404.
    """
    if not role_checks.can_manage_club(current_user, club_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You do not have permission to manage this club.",
        )
    return current_user
