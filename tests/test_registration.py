"""
Tests for the registration request flow.

Happy paths and all guards:
  - registration window must be open
  - player must not already have a registration this season
  - only the named player can decide
  - request cannot be decided twice
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser, get_current_user
from app.models.club import Club, ClubStatus
from app.models.player import Player
from app.models.registration import (
    PlayerSeasonRegistration,
    PlayerSeasonRegistrationStatus,
    RegistrationRequest,
    RegistrationRequestStatus,
)
from app.models.season import Season, SeasonStatus
from main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime.now(tz=UTC)


@pytest.fixture()
def club(db: Session) -> Club:
    c = Club(name="Wattala SC", code="WSC", status=ClubStatus.ACTIVE)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def player(db: Session) -> Player:
    p = Player(
        league_player_code="WL-0001",
        full_name="Kamal Perera",
        date_of_birth=datetime(1995, 6, 15).date(),
        nic_number="199516500123",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture()
def open_season(db: Session) -> Season:
    """Season that is OPEN with an active registration window."""
    s = Season(
        name="2025 Season",
        year=2025,
        registration_open_at=NOW - timedelta(days=1),
        registration_close_at=NOW + timedelta(days=30),
        status=SeasonStatus.OPEN,
        is_locked=False,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def closed_season(db: Session) -> Season:
    """Season whose registration window has already passed."""
    s = Season(
        name="2024 Season",
        year=2024,
        registration_open_at=NOW - timedelta(days=60),
        registration_close_at=NOW - timedelta(days=30),
        status=SeasonStatus.OPEN,
        is_locked=False,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _as_player(player: Player) -> None:
    """Override current_user to act as the given player."""
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=player.id, role="player", player_id=player.id
    )


def _as_admin() -> None:
    """Override current_user to act as an admin (no player_id)."""
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=999, role="admin"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_registration_request_success(
    client: TestClient, db: Session, club: Club, player: Player, open_season: Season
) -> None:
    _as_admin()
    response = client.post(
        "/registration-requests/",
        json={"player_id": player.id, "club_id": club.id, "season_id": open_season.id},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["player_id"] == player.id
    assert body["club_id"] == club.id
    assert body["status"] == "pending_player_confirmation"


def test_create_request_window_closed(
    client: TestClient, db: Session, club: Club, player: Player, closed_season: Season
) -> None:
    _as_admin()
    response = client.post(
        "/registration-requests/",
        json={
            "player_id": player.id,
            "club_id": club.id,
            "season_id": closed_season.id,
        },
    )
    assert response.status_code == 400
    assert "not open" in response.json()["detail"].lower()


def test_create_request_player_already_registered(
    client: TestClient, db: Session, club: Club, player: Player, open_season: Season
) -> None:
    # Seed an existing active registration for this player + season
    reg = PlayerSeasonRegistration(
        season_id=open_season.id,
        club_id=club.id,
        player_id=player.id,
        status=PlayerSeasonRegistrationStatus.ACTIVE,
    )
    db.add(reg)
    db.commit()

    _as_admin()
    response = client.post(
        "/registration-requests/",
        json={"player_id": player.id, "club_id": club.id, "season_id": open_season.id},
    )
    assert response.status_code == 400
    assert "already has a registration" in response.json()["detail"].lower()


def test_decide_accept_creates_active_registration(
    client: TestClient, db: Session, club: Club, player: Player, open_season: Season
) -> None:
    req = RegistrationRequest(
        season_id=open_season.id,
        club_id=club.id,
        player_id=player.id,
        requested_by_user_id=999,
        status=RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(req)
    db.commit()

    _as_player(player)
    response = client.post(
        f"/registration-requests/{req.id}/decide/", json={"decision": "accept"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

    # The PlayerSeasonRegistration must now exist and be ACTIVE
    db.expire_all()
    psr = db.execute(
        select(PlayerSeasonRegistration).where(
            PlayerSeasonRegistration.player_id == player.id,
            PlayerSeasonRegistration.season_id == open_season.id,
        )
    ).scalar_one()
    assert psr.status == PlayerSeasonRegistrationStatus.ACTIVE
    assert psr.club_id == club.id


def test_decide_reject_does_not_create_registration(
    client: TestClient, db: Session, club: Club, player: Player, open_season: Season
) -> None:
    req = RegistrationRequest(
        season_id=open_season.id,
        club_id=club.id,
        player_id=player.id,
        requested_by_user_id=999,
        status=RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(req)
    db.commit()

    _as_player(player)
    response = client.post(
        f"/registration-requests/{req.id}/decide/", json={"decision": "reject"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    db.expire_all()
    results = (
        db.execute(
            select(PlayerSeasonRegistration).where(
                PlayerSeasonRegistration.player_id == player.id,
                PlayerSeasonRegistration.season_id == open_season.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(results) == 0


def test_decide_wrong_player_is_forbidden(
    client: TestClient, db: Session, club: Club, player: Player, open_season: Season
) -> None:
    req = RegistrationRequest(
        season_id=open_season.id,
        club_id=club.id,
        player_id=player.id,
        requested_by_user_id=999,
        status=RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(req)
    db.commit()

    # Act as a different player (wrong id)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=42, role="player", player_id=player.id + 999
    )
    response = client.post(
        f"/registration-requests/{req.id}/decide/", json={"decision": "accept"}
    )
    assert response.status_code == 403


def test_decide_already_processed_is_rejected(
    client: TestClient, db: Session, club: Club, player: Player, open_season: Season
) -> None:
    req = RegistrationRequest(
        season_id=open_season.id,
        club_id=club.id,
        player_id=player.id,
        requested_by_user_id=999,
        status=RegistrationRequestStatus.ACCEPTED,  # already processed
    )
    db.add(req)
    db.commit()

    _as_player(player)
    response = client.post(
        f"/registration-requests/{req.id}/decide/", json={"decision": "accept"}
    )
    assert response.status_code == 400
    assert "already been processed" in response.json()["detail"].lower()
