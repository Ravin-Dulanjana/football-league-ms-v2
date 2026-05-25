"""
Tests for the release flow.

Happy paths and all guards:
  - registration must be ACTIVE to initiate a release
  - duplicate release must be rejected
  - only the named player can decide
  - release cannot be decided twice
  - on confirm: registration is atomically marked RELEASED
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
from app.models.season import Season, SeasonStatus
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
def season(db: Session) -> Season:
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


def _as_admin() -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=999, role="admin"
    )


_RELEASE_PAYLOAD = {
    "file_url": "https://storage.example.com/release-letter.pdf",
    "file_name": "release-letter.pdf",
}


# ---------------------------------------------------------------------------
# Tests — create release
# ---------------------------------------------------------------------------


def test_create_release_success(
    client: TestClient,
    db: Session,
    active_registration: PlayerSeasonRegistration,
) -> None:
    _as_admin()
    payload = {**_RELEASE_PAYLOAD, "registration_id": active_registration.id}
    response = client.post("/releases/", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["registration_id"] == active_registration.id
    assert body["status"] == "pending_player_confirmation"
    assert len(body["documents"]) == 1
    assert body["documents"][0]["file_name"] == "release-letter.pdf"


def test_create_release_registration_not_active(
    client: TestClient,
    db: Session,
    club: Club,
    player: Player,
    season: Season,
) -> None:
    released_reg = PlayerSeasonRegistration(
        season_id=season.id,
        club_id=club.id,
        player_id=player.id,
        registration_type=RegistrationType.NEW,
        status=PlayerSeasonRegistrationStatus.RELEASED,
    )
    db.add(released_reg)
    db.commit()

    _as_admin()
    payload = {**_RELEASE_PAYLOAD, "registration_id": released_reg.id}
    response = client.post("/releases/", json=payload)
    assert response.status_code == 400
    assert "active" in response.json()["detail"].lower()


def test_create_release_duplicate_rejected(
    client: TestClient,
    db: Session,
    active_registration: PlayerSeasonRegistration,
    player: Player,
    club: Club,
) -> None:
    # Seed an existing pending release
    existing_release = PlayerRelease(
        registration_id=active_registration.id,
        player_id=player.id,
        from_club_id=club.id,
        status=ReleaseStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(existing_release)
    db.commit()

    _as_admin()
    payload = {**_RELEASE_PAYLOAD, "registration_id": active_registration.id}
    response = client.post("/releases/", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests — decide release
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
            file_url="https://storage.example.com/letter.pdf",
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


def test_decide_reject_does_not_change_registration(
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

    _as_player(player)
    response = client.post(
        f"/releases/{release.id}/decide/", json={"decision": "reject"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

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
