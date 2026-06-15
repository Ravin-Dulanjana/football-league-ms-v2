"""
Club membership service.

Manages the permanent (cross-season) club membership of players:
  - A player is "free" when player.club_id is NULL
  - A club_admin can invite a free player to join their club
  - The player accepts or rejects the invite
  - On accept: player.club_id is set
  - On release (handled by release_service): player.club_id is cleared

The old season-based registration flow stays for historical records but new
club joining uses this service.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser
from app.middleware.logging import get_logger
from app.middleware.request_id import request_id_var
from app.models.club_membership import (
    ClubMembershipRequest,
    ClubMembershipRequestStatus,
)
from app.models.player import Player
from app.schemas.club_membership import ClubMembershipRequestCreate
from app.services import audit_service

logger = get_logger(__name__)


def get_all_requests(
    db: Session,
    current_user: CurrentUser,
) -> list[ClubMembershipRequest]:
    """
    Return club membership requests scoped by caller:
      club_admin — their own club's invites
      player     — invites for their own player_id
      league+    — all
    """
    q = select(ClubMembershipRequest).order_by(ClubMembershipRequest.id.desc())
    if current_user.role == "club_admin":
        if not current_user.club_id:
            return []
        q = q.where(ClubMembershipRequest.club_id == current_user.club_id)
    elif current_user.role == "player" and current_user.player_id:
        q = q.where(ClubMembershipRequest.player_id == current_user.player_id)
    return list(db.execute(q).scalars().all())


def get_request_by_id(db: Session, request_id: int) -> ClubMembershipRequest | None:
    return db.get(ClubMembershipRequest, request_id)


def create_invite(
    db: Session,
    data: ClubMembershipRequestCreate,
    current_user: CurrentUser,
) -> tuple[ClubMembershipRequest | None, str | None]:
    """
    Club admin invites a free player to join their club.

    Guards:
      - player must exist
      - player must be free (player.club_id is NULL)
      - no pending invite for this player+club already exists
    """
    logger.info(
        {
            "event": "club_membership_invite.start",
            "player_id": data.player_id,
            "club_id": current_user.club_id,
            "request_id": request_id_var.get(),
        }
    )

    player = db.get(Player, data.player_id)
    if player is None:
        return None, "Player not found."
    if player.club_id is not None:
        return None, (
            "This player is already in a club. "
            "They must be released before joining another club."
        )

    existing_pending = db.execute(
        select(ClubMembershipRequest).where(
            ClubMembershipRequest.player_id == data.player_id,
            ClubMembershipRequest.club_id == current_user.club_id,
            ClubMembershipRequest.status == ClubMembershipRequestStatus.PENDING,
        )
    ).scalar_one_or_none()
    if existing_pending is not None:
        return None, "A pending invite for this player already exists."

    req = ClubMembershipRequest(
        player_id=data.player_id,
        club_id=current_user.club_id,  # type: ignore[arg-type]
        requested_by_user_id=current_user.id,
        status=ClubMembershipRequestStatus.PENDING,
    )
    db.add(req)
    db.flush()
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="club_membership.invite",
        entity_type="ClubMembershipRequest",
        entity_id=req.id,
        details={"player_id": data.player_id, "club_id": current_user.club_id},
    )
    db.commit()
    db.refresh(req)
    logger.info(
        {
            "event": "club_membership_invite.complete",
            "request_id_db": req.id,
            "request_id": request_id_var.get(),
        }
    )
    return req, None


def decide_invite(
    db: Session,
    req: ClubMembershipRequest,
    decision: str,
    current_user: CurrentUser,
) -> tuple[ClubMembershipRequest | None, str | None]:
    """
    Player accepts or rejects a club membership invite.

    Guards:
      - caller must be the invited player
      - invite must still be PENDING
    On accept: player.club_id is set to the inviting club.
    """
    if current_user.player_id != req.player_id:
        return None, "Only the invited player can respond to this invite."
    if req.status != ClubMembershipRequestStatus.PENDING:
        return None, "This invite has already been responded to."
    if decision not in ("accept", "reject"):
        return None, "Decision must be 'accept' or 'reject'."

    now = datetime.now(tz=UTC)
    req.responded_at = now

    if decision == "accept":
        # Re-check: player still free?
        player = db.get(Player, req.player_id)
        if player is None:
            return None, "Player not found."
        if player.club_id is not None:
            req.status = ClubMembershipRequestStatus.CANCELLED
            db.commit()
            return None, ("Player is already in another club — invite cancelled.")
        req.status = ClubMembershipRequestStatus.ACCEPTED
        player.club_id = req.club_id
        db.flush()
        audit_service.write_audit_log(
            db,
            actor_id=current_user.id,
            action="club_membership.accepted",
            entity_type="ClubMembershipRequest",
            entity_id=req.id,
            details={"club_id": req.club_id},
        )
    else:
        req.status = ClubMembershipRequestStatus.REJECTED
        db.flush()
        audit_service.write_audit_log(
            db,
            actor_id=current_user.id,
            action="club_membership.rejected",
            entity_type="ClubMembershipRequest",
            entity_id=req.id,
        )

    db.commit()
    db.refresh(req)
    return req, None


def cancel_invite(
    db: Session,
    req: ClubMembershipRequest,
    current_user: CurrentUser,
) -> tuple[ClubMembershipRequest | None, str | None]:
    """Club admin can cancel their own pending invite."""
    if current_user.club_id != req.club_id:
        return None, "You can only cancel invites from your own club."
    if req.status != ClubMembershipRequestStatus.PENDING:
        return None, "Only pending invites can be cancelled."
    req.status = ClubMembershipRequestStatus.CANCELLED
    db.commit()
    db.refresh(req)
    return req, None


def release_player(
    db: Session,
    player: Player,
    current_user: CurrentUser,
) -> tuple[Player | None, str | None]:
    """
    Club admin releases a player from their club.

    Guards:
      - player must be in the caller's club
      - should not be in an ACTIVE season roster (checked in registration_service)
    """
    if player.club_id != current_user.club_id:
        return None, "You can only release players from your own club."
    if player.club_id is None:
        return None, "Player is not currently in any club."

    player.club_id = None
    db.commit()
    db.refresh(player)
    audit_service.write_audit_log(
        db,
        actor_id=current_user.id,
        action="club_membership.released",
        entity_type="Player",
        entity_id=player.id,
        details={"released_by_club_id": current_user.club_id},
    )
    return player, None
