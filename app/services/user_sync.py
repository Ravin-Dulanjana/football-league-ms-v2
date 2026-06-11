"""
Cognito user synchronisation.

On every authenticated request, `get_or_create_user` looks up the User
shadow record in PostgreSQL by Cognito sub. If no record exists (first
ever request from this user), it creates one.

The role, club_id, and player_id are sourced from the JWT claims so they
always reflect the current state of the Cognito custom attributes — an
admin can change a user's role in Cognito and the next request will pick
up the change.

Side effects on every successful auth
──────────────────────────────────────
- users.last_login_at is updated to now().
- If the user has a linked player profile in pending_claim status, it is
  transitioned to "active" (claiming the profile for real).

Performance note
────────────────
This executes one indexed SELECT (and one UPDATE) per authenticated request.
For high-traffic production systems, cache `cognito_sub → CurrentUser`
in Redis with a TTL matching the JWT lifetime.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser
from app.models.player import Player, PlayerStatus
from app.models.user import User


def get_or_create_user(db: Session, claims: dict) -> CurrentUser:
    """
    Look up or create the PostgreSQL User record for a Cognito user,
    then return a CurrentUser populated from the JWT claims.

    Also:
    - Always stamps last_login_at = now() so the dashboard shows the real
      last-seen time.
    - Transitions pending_claim player profiles to active on first login.

    Claims expected (from Cognito ID token):
        sub              — Cognito user UUID (immutable)
        email            — verified email address
        custom:role      — one of: super_admin, league_admin, club_admin,
                           club_staff, player
        custom:club_id   — PostgreSQL Club.id (club_admin only, as string)
        custom:player_id — PostgreSQL Player.id (player, as string)
    """
    cognito_sub: str = claims["sub"]
    email: str = claims.get("email", "")
    role: str = claims.get("custom:role", "")

    # Cognito NumberAttribute values arrive as strings in JWT claims
    raw_club_id = claims.get("custom:club_id", "")
    raw_player_id = claims.get("custom:player_id", "")
    club_id: int | None = int(raw_club_id) if raw_club_id else None
    player_id: int | None = int(raw_player_id) if raw_player_id else None

    now = datetime.now(tz=UTC)

    user = db.execute(
        select(User).where(User.cognito_sub == cognito_sub)
    ).scalar_one_or_none()

    if user is None:
        user = User(
            cognito_sub=cognito_sub,
            email=email,
            role=role,
            club_id=club_id,
            player_id=player_id,
            last_login_at=now,
        )
        db.add(user)
        db.flush()
        # Transition pending_claim player to active on first login
        _activate_player_if_pending(db, player_id)
        db.commit()
        db.refresh(user)
        return CurrentUser(
            id=user.id,
            cognito_sub=cognito_sub,
            email=email,
            role=role,
            club_id=club_id,
            player_id=player_id,
        )

    # Sync any attribute changes made in Cognito since last login and
    # always update last_login_at.
    user.last_login_at = now
    if (
        user.email != email
        or user.role != role
        or user.club_id != club_id
        or user.player_id != player_id
    ):
        user.email = email
        user.role = role
        user.club_id = club_id
        user.player_id = player_id

    db.flush()
    # Transition pending_claim → active every time (handles the case where the
    # user was created by an admin but hasn't logged in yet — status is still
    # pending_claim until now).
    _activate_player_if_pending(db, player_id)
    db.commit()

    return CurrentUser(
        id=user.id,
        cognito_sub=cognito_sub,
        email=email,
        role=role,
        club_id=club_id,
        player_id=player_id,
    )


def _activate_player_if_pending(db: Session, player_id: int | None) -> None:
    """
    If the linked player profile is in 'pending_claim' status, transition it
    to 'active' — the user has now claimed their profile by logging in.
    """
    if not player_id:
        return
    player = db.get(Player, player_id)
    if player is not None and player.status == PlayerStatus.PENDING_CLAIM:
        player.status = PlayerStatus.ACTIVE
        db.flush()
