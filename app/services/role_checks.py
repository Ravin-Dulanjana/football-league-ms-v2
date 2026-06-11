"""
Role-check helper functions.

These are pure boolean functions — they take a CurrentUser (and optionally a
club_id) and return True/False.  No HTTPException is raised here; that lives
in the dependency layer (app/dependencies/roles.py).

Why a separate module rather than methods on CurrentUser?
  CurrentUser is a thin data class (no methods) by design.  Keeping logic here
  keeps CurrentUser importable without pulling in any business-rule baggage.
  It also mirrors V1's role_checks.py exactly, making the two codebases easy
  to compare.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.dependencies import CurrentUser


def is_super_admin(user: CurrentUser) -> bool:
    """True if the user holds the super_admin role."""
    return user.role == "super_admin"


def is_league_admin(user: CurrentUser) -> bool:
    """True if the user holds the league_admin role."""
    return user.role == "league_admin"


def is_club_admin(user: CurrentUser, club_id: int) -> bool:
    """
    True if the user is a club_admin AND their account is linked to this club.

    A club_admin with club_id=3 returns False for club_id=5 even though both
    are club_admin role — the role alone is not enough, the club must match.
    """
    return user.role == "club_admin" and user.club_id == club_id


def can_manage_club(user: CurrentUser, club_id: int) -> bool:
    """
    True if the user can perform write operations on a specific club.

    Hierarchy:
      super_admin    — can manage any club unconditionally
      league_admin   — can manage any club in the league (single-league system)
      club_admin     — can only manage their own club (club_id must match)
      player / other — cannot manage any club
    """
    if is_super_admin(user) or is_league_admin(user):
        return True
    return is_club_admin(user, club_id)


def is_club_staff(user: CurrentUser) -> bool:
    """True if the user's primary role is club_staff (no governance role)."""
    return user.role == "club_staff"


def is_base_club_member(user: CurrentUser) -> bool:
    """
    True if the user is a base club member (player or club_staff) with no
    additional governance role. They can see their own club activity but
    cannot perform administrative actions.
    """
    return user.role in {"player", "club_staff"}


def has_any_admin_role(user: CurrentUser) -> bool:
    """
    True if the user holds any administrative role.

    Used to gate endpoints that require *some* admin privilege but don't
    need to distinguish which specific admin tier (e.g. export endpoints
    that are scoped differently per role but all admins can hit).
    """
    return user.role in {"super_admin", "league_admin", "club_admin"}


def has_user_management_scope(user: CurrentUser) -> bool:
    """
    True if the user can list and create user accounts.

    super_admin — full user management (all roles, soft-delete, account actions)
    league_admin — limited management (create club_admin only, no soft-delete)
    """
    return user.role in {"super_admin", "league_admin"}
