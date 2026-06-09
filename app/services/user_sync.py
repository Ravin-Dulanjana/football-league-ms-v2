"""
Cognito user synchronisation.

On every authenticated request, `get_or_create_user` looks up the User
shadow record in PostgreSQL by Cognito sub. If no record exists (first
ever request from this user), it creates one.

The role, club_id, and player_id are sourced from the JWT claims so they
always reflect the current state of the Cognito custom attributes — an
admin can change a user's role in Cognito and the next request will pick
up the change.

Performance note
────────────────
This executes one indexed SELECT (and occasionally an INSERT or UPDATE)
per authenticated request. For high-traffic production systems, cache
`cognito_sub → CurrentUser` in Redis with a TTL matching the JWT lifetime.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser
from app.models.user import User


def get_or_create_user(db: Session, claims: dict) -> CurrentUser:
    """
    Look up or create the PostgreSQL User record for a Cognito user,
    then return a CurrentUser populated from the JWT claims.

    Claims expected (from Cognito ID token):
        sub             — Cognito user UUID (immutable)
        email           — verified email address
        custom:role     — one of: super_admin, league_admin, club_admin, player
        custom:club_id  — PostgreSQL Club.id (club_admin only, stored as string)
        custom:player_id — PostgreSQL Player.id (player only, stored as string)
    """
    cognito_sub: str = claims["sub"]
    email: str = claims.get("email", "")
    role: str = claims.get("custom:role", "")

    # Cognito NumberAttribute values arrive as strings in JWT claims
    raw_club_id = claims.get("custom:club_id", "")
    raw_player_id = claims.get("custom:player_id", "")
    club_id: int | None = int(raw_club_id) if raw_club_id else None
    player_id: int | None = int(raw_player_id) if raw_player_id else None

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
        )
        db.add(user)
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

    # Sync any attribute changes made in Cognito since last login
    needs_update = (
        user.email != email
        or user.role != role
        or user.club_id != club_id
        or user.player_id != player_id
    )
    if needs_update:
        user.email = email
        user.role = role
        user.club_id = club_id
        user.player_id = player_id
        db.commit()

    return CurrentUser(
        id=user.id,
        cognito_sub=cognito_sub,
        email=email,
        role=role,
        club_id=club_id,
        player_id=player_id,
    )
