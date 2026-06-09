"""
Tests for app/services/events.py (publish_event) and the integration
between service functions and event publishing.

Design:
  - All existing tests keep passing because settings.sqs_queue_url defaults
    to "" — publish_event short-circuits before touching boto3.
  - Tests here set a fake queue URL via monkeypatch and mock boto3 so no
    real AWS calls are ever made.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser, get_current_user
from app.models.club import Club, ClubStatus
from app.models.player import Player
from app.models.registration import (
    PlayerSeasonRegistration,
    PlayerSeasonRegistrationStatus,
    RegistrationRequest,
    RegistrationRequestStatus,
    RegistrationType,
)
from app.models.release import PlayerRelease, ReleaseDocument, ReleaseStatus
from app.models.season import Season, SeasonStatus
from app.services import events as events_module
from main import app

NOW = datetime.now(tz=UTC)
FAKE_QUEUE_URL = "https://sqs.ap-southeast-1.amazonaws.com/123456789/test-queue"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def club_with_email(db: Session) -> Club:
    c = Club(
        name="Wattala SC",
        code="WSC",
        status=ClubStatus.ACTIVE,
        email="admin@wattalasc.com",
    )
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
def pending_request(
    db: Session,
    club_with_email: Club,
    player: Player,
    open_season: Season,
) -> RegistrationRequest:
    req = RegistrationRequest(
        season_id=open_season.id,
        club_id=club_with_email.id,
        player_id=player.id,
        requested_by_user_id=1,
        status=RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@pytest.fixture()
def active_registration(
    db: Session,
    club_with_email: Club,
    player: Player,
    open_season: Season,
) -> PlayerSeasonRegistration:
    reg = PlayerSeasonRegistration(
        season_id=open_season.id,
        club_id=club_with_email.id,
        player_id=player.id,
        registration_type=RegistrationType.NEW,
        status=PlayerSeasonRegistrationStatus.ACTIVE,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


# ---------------------------------------------------------------------------
# Unit tests — publish_event itself
# ---------------------------------------------------------------------------


def test_publish_event_sends_correct_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    """publish_event constructs the expected message envelope and calls send_message."""
    monkeypatch.setattr(events_module.settings, "sqs_queue_url", FAKE_QUEUE_URL)

    with patch("app.services.events.boto3") as mock_boto3:
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs

        events_module.publish_event(
            "registration.requested",
            {"player_name": "Kamal", "recipient_email": "club@example.com"},
        )

        mock_boto3.client.assert_called_once_with("sqs", region_name="ap-southeast-1")
        mock_sqs.send_message.assert_called_once()

        call_kwargs = mock_sqs.send_message.call_args[1]
        assert call_kwargs["QueueUrl"] == FAKE_QUEUE_URL

        body = json.loads(call_kwargs["MessageBody"])
        assert body["event_type"] == "registration.requested"
        assert body["version"] == "1.0"
        assert body["payload"]["player_name"] == "Kamal"
        assert "timestamp" in body  # ISO 8601 string


def test_publish_event_skips_when_no_queue_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """publish_event does nothing when SQS_QUEUE_URL is empty (local dev default)."""
    monkeypatch.setattr(events_module.settings, "sqs_queue_url", "")

    with patch("app.services.events.boto3") as mock_boto3:
        events_module.publish_event("registration.requested", {})
        mock_boto3.client.assert_not_called()


def test_publish_event_survives_sqs_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    publish_event does NOT re-raise when SQS send_message throws.
    The business transaction must not fail because SQS is unavailable.
    """
    monkeypatch.setattr(events_module.settings, "sqs_queue_url", FAKE_QUEUE_URL)

    with patch("app.services.events.boto3") as mock_boto3:
        mock_sqs = MagicMock()
        mock_sqs.send_message.side_effect = RuntimeError("SQS connection error")
        mock_boto3.client.return_value = mock_sqs

        # Must not raise
        events_module.publish_event("registration.requested", {})


# ---------------------------------------------------------------------------
# Integration tests — event published from service functions via FastAPI
# ---------------------------------------------------------------------------


def test_accept_registration_publishes_accepted_event(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    pending_request: RegistrationRequest,
    player: Player,
    club_with_email: Club,
    open_season: Season,
) -> None:
    """
    When a player accepts a registration request, the service publishes a
    'registration.accepted' event with the correct payload structure.
    """
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=player.id, role="player", player_id=player.id
    )
    monkeypatch.setattr(events_module.settings, "sqs_queue_url", FAKE_QUEUE_URL)

    with patch("app.services.events.boto3") as mock_boto3:
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs

        response = client.post(
            f"/registration-requests/{pending_request.id}/decide/",
            json={"decision": "accept"},
        )
        assert response.status_code == 200

        mock_sqs.send_message.assert_called_once()
        body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])

        assert body["event_type"] == "registration.accepted"
        assert body["payload"]["player_name"] == player.full_name
        assert body["payload"]["club_name"] == club_with_email.name
        assert body["payload"]["season_name"] == open_season.name
        assert body["payload"]["recipient_email"] == club_with_email.email


def test_confirm_release_publishes_release_confirmed_event(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    active_registration: PlayerSeasonRegistration,
    player: Player,
    club_with_email: Club,
    db: Session,
) -> None:
    """
    When a player confirms a release, the service publishes a
    'release.confirmed' event with the correct payload structure.
    """
    release = PlayerRelease(
        registration_id=active_registration.id,
        player_id=player.id,
        from_club_id=club_with_email.id,
        status=ReleaseStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(release)
    db.flush()
    db.add(
        ReleaseDocument(
            release_id=release.id,
            s3_key="releases/documents/letter.pdf",
            file_name="letter.pdf",
        )
    )
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=player.id, role="player", player_id=player.id
    )
    monkeypatch.setattr(events_module.settings, "sqs_queue_url", FAKE_QUEUE_URL)

    with patch("app.services.events.boto3") as mock_boto3:
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs

        response = client.post(
            f"/releases/{release.id}/decide/", json={"decision": "confirm"}
        )
        assert response.status_code == 200

        mock_sqs.send_message.assert_called_once()
        body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])

        assert body["event_type"] == "release.confirmed"
        assert body["payload"]["player_name"] == player.full_name
        assert body["payload"]["club_name"] == club_with_email.name
        assert body["payload"]["recipient_email"] == club_with_email.email
