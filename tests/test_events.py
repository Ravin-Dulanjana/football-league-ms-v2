"""
Tests for the Transactional Outbox pattern in app/services/events.py.

Architecture
────────────
1. queue_event(db, event_type, payload)  — writes OutboxEvent row to DB.
   Must be called BEFORE db.commit() so it's atomic with the business write.

2. publish_pending(db)  — reads unsent rows, sends to SQS, marks sent=True.
   Called by the APScheduler relay every ~300 ms.

Test design
───────────
- All tests run against in-memory SQLite (the conftest.py fixture creates all
  tables, including outbox_events, via Base.metadata.create_all).
- SQS calls are mocked via unittest.mock — no real AWS calls.
- settings.sqs_queue_url defaults to "" so queue_event skips silently;
  tests that want to exercise the outbox set it via monkeypatch.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser, get_current_user
from app.models.club import Club, ClubStatus
from app.models.outbox import OutboxEvent
from app.models.player import Player
from app.models.registration import (
    PlayerSeasonRegistration,
    PlayerSeasonRegistrationStatus,
    RegistrationRequest,
    RegistrationRequestStatus,
    RegistrationType,
)
from app.models.release import PlayerRelease, ReleaseDocument, ReleaseStatus
from app.models.season import Season
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
# Unit tests — queue_event
# ---------------------------------------------------------------------------


def test_queue_event_writes_outbox_row(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """queue_event inserts an OutboxEvent row with sent=False."""
    monkeypatch.setattr(events_module.settings, "sqs_queue_url", FAKE_QUEUE_URL)

    events_module.queue_event(
        db,
        "registration.requested",
        {"player_name": "Kamal", "recipient_email": "club@example.com"},
    )
    db.commit()

    rows = db.execute(select(OutboxEvent)).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == "registration.requested"
    assert row.sent is False
    payload = json.loads(row.payload_json)
    assert payload["player_name"] == "Kamal"


def test_queue_event_skips_when_no_queue_url(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """queue_event writes nothing when SQS_QUEUE_URL is empty (local dev default)."""
    monkeypatch.setattr(events_module.settings, "sqs_queue_url", "")

    events_module.queue_event(db, "registration.requested", {})
    db.commit()

    rows = db.execute(select(OutboxEvent)).scalars().all()
    assert rows == []


# ---------------------------------------------------------------------------
# Unit tests — publish_pending (the relay)
# ---------------------------------------------------------------------------


def test_publish_pending_sends_correct_structure(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """publish_pending sends the expected message envelope to SQS."""
    monkeypatch.setattr(events_module.settings, "sqs_queue_url", FAKE_QUEUE_URL)

    # Insert an unsent outbox row directly (simulating what queue_event does).
    row = OutboxEvent(
        event_type="registration.requested",
        payload_json=json.dumps({"player_name": "Kamal"}),
        created_at=datetime.now(tz=UTC),
    )
    db.add(row)
    db.commit()

    with patch("app.services.events.boto3") as mock_boto3:
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs

        events_module.publish_pending(db)

        mock_boto3.client.assert_called_once_with("sqs", region_name="ap-southeast-1")
        mock_sqs.send_message.assert_called_once()
        call_kwargs = mock_sqs.send_message.call_args[1]
        assert call_kwargs["QueueUrl"] == FAKE_QUEUE_URL

        body = json.loads(call_kwargs["MessageBody"])
        assert body["event_type"] == "registration.requested"
        assert body["version"] == "1.0"
        assert body["payload"]["player_name"] == "Kamal"
        assert "timestamp" in body

    # Row should now be marked sent.
    db.refresh(row)
    assert row.sent is True
    assert row.sent_at is not None


def test_publish_pending_survives_sqs_failure(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """publish_pending does NOT reraise on SQS failure — row stays unsent for retry."""
    monkeypatch.setattr(events_module.settings, "sqs_queue_url", FAKE_QUEUE_URL)

    row = OutboxEvent(
        event_type="registration.requested",
        payload_json=json.dumps({}),
        created_at=datetime.now(tz=UTC),
    )
    db.add(row)
    db.commit()

    with patch("app.services.events.boto3") as mock_boto3:
        mock_sqs = MagicMock()
        mock_sqs.send_message.side_effect = RuntimeError("SQS connection error")
        mock_boto3.client.return_value = mock_sqs

        # Must not raise
        events_module.publish_pending(db)

    db.refresh(row)
    assert row.sent is False  # not marked sent — will be retried next tick


# ---------------------------------------------------------------------------
# Integration tests — event queued from service functions via FastAPI
# ---------------------------------------------------------------------------


def test_accept_registration_queues_accepted_event(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    pending_request: RegistrationRequest,
    player: Player,
    club_with_email: Club,
    open_season: Season,
) -> None:
    """
    When a player accepts a registration request the service writes a
    'registration.accepted' OutboxEvent row (the relay publishes it later).
    """
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=player.id, role="player", player_id=player.id
    )
    monkeypatch.setattr(events_module.settings, "sqs_queue_url", FAKE_QUEUE_URL)

    response = client.post(
        f"/registration-requests/{pending_request.id}/decide/",
        json={"decision": "accept"},
    )
    assert response.status_code == 200

    rows = (
        db.execute(
            select(OutboxEvent).where(OutboxEvent.event_type == "registration.accepted")
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    payload = json.loads(rows[0].payload_json)
    assert payload["player_name"] == player.full_name
    assert payload["club_name"] == club_with_email.name
    assert payload["season_name"] == open_season.name
    assert payload["recipient_email"] == club_with_email.email


def test_confirm_release_queues_release_confirmed_event(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    active_registration: PlayerSeasonRegistration,
    player: Player,
    club_with_email: Club,
) -> None:
    """
    When a player confirms a release the service writes a 'release.confirmed'
    OutboxEvent row.
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

    response = client.post(
        f"/releases/{release.id}/decide/", json={"decision": "confirm"}
    )
    assert response.status_code == 200

    rows = (
        db.execute(
            select(OutboxEvent).where(OutboxEvent.event_type == "release.confirmed")
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    payload = json.loads(rows[0].payload_json)
    assert payload["player_name"] == player.full_name
    assert payload["club_name"] == club_with_email.name
    assert payload["recipient_email"] == club_with_email.email
