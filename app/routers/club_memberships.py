from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user, require_role
from app.models.club_membership import ClubMembershipRequest
from app.models.player import Player
from app.schemas.club_membership import (
    ClubMembershipDecide,
    ClubMembershipRequestCreate,
    ClubMembershipRequestRead,
)
from app.schemas.player import PlayerRead
from app.services import club_membership_service, player_service

router = APIRouter(prefix="/club-memberships", tags=["club-memberships"])


@router.get("/requests/", response_model=list[ClubMembershipRequestRead])
def list_requests(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ClubMembershipRequest]:
    """
    List club membership invites.
    club_admin → their club's sent invites.
    player     → invites they have received.
    league+    → all invites.
    """
    return club_membership_service.get_all_requests(db, current_user)


@router.post(
    "/requests/",
    response_model=ClubMembershipRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invite(
    data: ClubMembershipRequestCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_role("super_admin", "league_admin", "club_admin")
    ),
) -> ClubMembershipRequest:
    """Send a club membership invite to a free player."""
    if current_user.role == "club_admin" and not current_user.club_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Your account is not linked to a club.",
        )
    req, error = club_membership_service.create_invite(db, data, current_user)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)
    return req  # type: ignore[return-value]


@router.post("/requests/{request_id}/decide/", response_model=ClubMembershipRequestRead)
def decide_invite(
    request_id: int,
    data: ClubMembershipDecide,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("player")),
) -> ClubMembershipRequest:
    """Player accepts or rejects a club membership invite."""
    req = club_membership_service.get_request_by_id(db, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found.")
    updated, error = club_membership_service.decide_invite(
        db, req, data.decision, current_user
    )
    if error:
        code = (
            status.HTTP_403_FORBIDDEN
            if "Only the" in error
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, error)
    return updated  # type: ignore[return-value]


@router.post("/requests/{request_id}/cancel/", response_model=ClubMembershipRequestRead)
def cancel_invite(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_role("super_admin", "league_admin", "club_admin")
    ),
) -> ClubMembershipRequest:
    """Club admin cancels a pending invite they sent."""
    req = club_membership_service.get_request_by_id(db, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found.")
    updated, error = club_membership_service.cancel_invite(db, req, current_user)
    if error:
        code = (
            status.HTTP_403_FORBIDDEN
            if "only" in error.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, error)
    return updated  # type: ignore[return-value]


@router.get("/free-players/", response_model=list[PlayerRead])
def list_free_players(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_role("super_admin", "league_admin", "club_admin")),
) -> list[Player]:
    """Return players who are not currently in any club (player.club_id is NULL)."""
    return player_service.get_all_players(db, free_only=True)


@router.post("/release/{player_id}/", response_model=PlayerRead)
def release_player(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("club_admin")),
) -> Player:
    """Club admin releases a player from their club (clears club_id)."""
    player = player_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found.")
    updated, error = club_membership_service.release_player(db, player, current_user)
    if error:
        code = (
            status.HTTP_403_FORBIDDEN
            if "only" in error.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, error)
    return updated  # type: ignore[return-value]
