"""
Tests for the release flow.

Happy paths and all guards:
  - player must be in the caller's club to initiate a release
  - player not in any club is rejected
  - player in a different club is rejected
  - only the named player can decide (legacy PENDING records)
  - release cannot be decided twice
  - on decide confirm: registration is atomically marked RELEASED
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser, get_current_user
from app.models.club import Club, ClubStatus
from app.models.player import Player
from app.models.registration import (
    PlayerSeasonRegistration,
    PlayerSeasonRegistrationStatus,
    RegistrationType,
)
from app.models.release import PlayerRelease, ReleaseDocument, ReleaseStatus
from app.models.season import Season
from main import app

NOW = datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def club(db: Session) -> Club:
    c = Club(name="Wattala SC", code="WSC", status=ClubStatus.ACTIVE)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def other_club(db: Session) -> Club:
    c = Club(name="Colombo FC", code="CFC", status=ClubStatus.ACTIVE)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def player(db: Session, club: Club) -> Player:
    p = Player(
        league_player_code="WL-0001",
        full_name="Kamal Perera",
        date_of_birth=datetime(1995, 6, 15).date(),
        nic_number="199516500123",
        club_id=club.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture()
def season(db: Session) -> Season:
    s = Season(
        name="2025 Season",
        year=2025,
        registration_open_at=NOW - timedelta(days=1),
        registration_close_at=NOW + timedelta(days=30),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def active_registration(
    db: Session, club: Club, player: Player, season: Season
) -> PlayerSeasonRegistration:
    reg = PlayerSeasonRegistration(
        season_id=season.id,
        club_id=club.id,
        player_id=player.id,
        registration_type=RegistrationType.NEW,
        status=PlayerSeasonRegistrationStatus.ACTIVE,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


def _as_player(player: Player) -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=player.id, role="player", player_id=player.id
    )


def _as_club_admin(club: Club) -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=999, role="club_admin", club_id=club.id
    )


_RELEASE_PAYLOAD = {
    # s3_key: the S3 object key returned by POST /releases/document-upload-url/
    # In tests we use a hard-coded key — in production this comes from S3.
    "s3_key": "releases/documents/test-uuid.pdf",
    "file_name": "release-letter.pdf",
}


# ---------------------------------------------------------------------------
# Tests — create release (new direct flow: player_id, immediate CONFIRMED)
# ---------------------------------------------------------------------------


def test_create_release_success(
    client: TestClient,
    db: Session,
    player: Player,
    club: Club,
) -> None:
    """Club admin releases a player who is in their club — immediate CONFIRMED."""
    _as_club_admin(club)
    payload = {**_RELEASE_PAYLOAD, "player_id": player.id}
    response = client.post("/releases/", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["player_id"] == player.id
    assert body["from_club_id"] == club.id
    assert body["status"] == "confirmed"
    assert body["registration_id"] is None
    assert len(body["documents"]) == 1
    assert body["documents"][0]["file_name"] == "release-letter.pdf"
    assert body["documents"][0]["s3_key"] == "releases/documents/test-uuid.pdf"

    # Player club_id must be cleared immediately
    db.expire_all()
    db.refresh(player)
    assert player.club_id is None


def test_create_release_player_not_in_club(
    client: TestClient,
    db: Session,
    club: Club,
) -> None:
    """Releasing a player who is not in any club returns 400."""
    free_player = Player(
        league_player_code="WL-FREE",
        full_name="Free Agent",
        date_of_birth=datetime(1998, 1, 1).date(),
        nic_number="199800100001",
        club_id=None,
    )
    db.add(free_player)
    db.commit()

    _as_club_admin(club)
    payload = {**_RELEASE_PAYLOAD, "player_id": free_player.id}
    response = client.post("/releases/", json=payload)
    assert response.status_code == 400
    assert "own club" in response.json()["detail"].lower()


def test_create_release_player_in_different_club(
    client: TestClient,
    db: Session,
    club: Club,
    other_club: Club,
) -> None:
    """Club admin cannot release a player from a different club."""
    other_player = Player(
        league_player_code="WL-OTHER",
        full_name="Other Club Player",
        date_of_birth=datetime(1997, 5, 5).date(),
        nic_number="199705050001",
        club_id=other_club.id,
    )
    db.add(other_player)
    db.commit()

    _as_club_admin(club)
    payload = {**_RELEASE_PAYLOAD, "player_id": other_player.id}
    response = client.post("/releases/", json=payload)
    assert response.status_code == 400
    assert "own club" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests — decide release (legacy PENDING_PLAYER_CONFIRMATION records)
# ---------------------------------------------------------------------------


def test_decide_confirm_marks_registration_released(
    client: TestClient,
    db: Session,
    active_registration: PlayerSeasonRegistration,
    player: Player,
    club: Club,
) -> None:
    release = PlayerRelease(
        registration_id=active_registration.id,
        player_id=player.id,
        from_club_id=club.id,
        status=ReleaseStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(release)
    db.flush()
    db.add(
        ReleaseDocument(
            release_id=release.id,
            s3_key="releases/documents/test-letter.pdf",
            file_name="letter.pdf",
        )
    )
    db.commit()

    _as_player(player)
    response = client.post(
        f"/releases/{release.id}/decide/", json={"decision": "confirm"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    # Registration must be RELEASED atomically
    db.expire_all()
    db.refresh(active_registration)
    assert active_registration.status == PlayerSeasonRegistrationStatus.RELEASED
    assert active_registration.released_at is not None


def test_decide_reject_is_no_longer_valid(
    client: TestClient,
    db: Session,
    active_registration: PlayerSeasonRegistration,
    player: Player,
    club: Club,
) -> None:
    """Players can only confirm a release; 'reject' is no longer a valid decision."""
    release = PlayerRelease(
        registration_id=active_registration.id,
        player_id=player.id,
        from_club_id=club.id,
        status=ReleaseStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(release)
    db.commit()

    _as_player(player)
    response = client.post(
        f"/releases/{release.id}/decide/", json={"decision": "reject"}
    )
    assert response.status_code == 422  # schema no longer accepts "reject"

    # Registration must remain ACTIVE — the release was not processed
    db.expire_all()
    db.refresh(active_registration)
    assert active_registration.status == PlayerSeasonRegistrationStatus.ACTIVE


def test_decide_wrong_player_is_forbidden(
    client: TestClient,
    db: Session,
    active_registration: PlayerSeasonRegistration,
    player: Player,
    club: Club,
) -> None:
    release = PlayerRelease(
        registration_id=active_registration.id,
        player_id=player.id,
        from_club_id=club.id,
        status=ReleaseStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(release)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=42, role="player", player_id=player.id + 999
    )
    response = client.post(
        f"/releases/{release.id}/decide/", json={"decision": "confirm"}
    )
    assert response.status_code == 403


def test_decide_already_processed_is_rejected(
    client: TestClient,
    db: Session,
    active_registration: PlayerSeasonRegistration,
    player: Player,
    club: Club,
) -> None:
    release = PlayerRelease(
        registration_id=active_registration.id,
        player_id=player.id,
        from_club_id=club.id,
        status=ReleaseStatus.CONFIRMED,  # already processed
    )
    db.add(release)
    db.commit()

    _as_player(player)
    response = client.post(
        f"/releases/{release.id}/decide/", json={"decision": "confirm"}
    )
    assert response.status_code == 400
    assert "already been processed" in response.json()["detail"].lower()
