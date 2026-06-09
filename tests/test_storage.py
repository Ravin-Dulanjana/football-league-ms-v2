"""
Tests for app/services/storage.py.

All tests mock boto3 — no real AWS calls are made.

WHY MOCK boto3 (not use moto or real AWS):
  - moto is an excellent library but adds a dev dependency and requires
    knowing which moto fixtures to set up.
  - Real AWS calls make tests slow (~200ms each) and require credentials.
  - unittest.mock.patch is built into the stdlib and patches a single
    function, which is precise and explicit.

PATCHING STRATEGY:
  We patch "app.services.storage.boto3" — the boto3 name as it is
  imported inside storage.py.  If we patched "boto3.client" globally,
  any other boto3 call anywhere in the process would also be affected.
  Patching the local reference (where the code actually uses it) is
  the correct approach.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
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
    RegistrationType,
)
from app.models.release import ReleaseDocument
from app.models.season import Season, SeasonStatus
from app.services import storage
from main import app

NOW = datetime.now(tz=UTC)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_PRESIGNED_RESPONSE: dict[str, Any] = {
    "url": "https://football-league-media.s3.amazonaws.com/",
    "fields": {
        "key": "clubs/logos/fake-uuid.jpg",
        "AWSAccessKeyId": "FAKEKEY",
        "policy": "FAKEPOLICY==",
        "signature": "FAKESIG==",
        "Content-Type": "image/jpeg",
    },
}


def _mock_s3_client(presigned_response: dict[str, Any]) -> MagicMock:
    """
    Build a mock boto3 S3 client whose generate_presigned_post
    returns the given response dict.
    """
    mock_client = MagicMock()
    mock_client.generate_presigned_post.return_value = presigned_response
    return mock_client


# ---------------------------------------------------------------------------
# Unit tests — storage service functions directly
# ---------------------------------------------------------------------------


def test_generate_upload_url_structure() -> None:
    """
    generate_upload_url should return a dict with the four expected keys:
    url, fields, key, expires_in.

    The key must start with the requested folder prefix and end with the
    original file extension.
    """
    mock_client = _mock_s3_client(FAKE_PRESIGNED_RESPONSE)

    with patch("app.services.storage.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client

        result = storage.generate_upload_url(
            folder="clubs/logos",
            filename="my-logo.jpg",
            content_type="image/jpeg",
        )

    # The function must call boto3.client("s3", region_name=...)
    mock_boto3.client.assert_called_once()
    call_args = mock_boto3.client.call_args
    assert call_args[0][0] == "s3"

    # The presigned_post must have been called with a key under the folder
    mock_client.generate_presigned_post.assert_called_once()
    post_call_kwargs = mock_client.generate_presigned_post.call_args[1]
    assert post_call_kwargs["Key"].startswith("clubs/logos/")
    assert post_call_kwargs["Key"].endswith(".jpg")
    assert post_call_kwargs["ExpiresIn"] == 900

    # The returned dict must have all required keys
    assert "url" in result
    assert "fields" in result
    assert "key" in result
    assert result["expires_in"] == 900

    # key in result must match what was passed to generate_presigned_post
    assert result["key"] == post_call_kwargs["Key"]


def test_generate_upload_url_extension_fallback() -> None:
    """
    If the filename has no extension, the key should end with ".bin"
    (safe unknown-binary fallback).
    """
    mock_client = _mock_s3_client(FAKE_PRESIGNED_RESPONSE)

    with patch("app.services.storage.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client
        result = storage.generate_upload_url(
            folder="releases/documents",
            filename="nodothere",
            content_type="application/octet-stream",
        )

    assert str(result["key"]).endswith(".bin")


def test_generate_upload_url_conditions_include_size_limit() -> None:
    """
    The signed policy must include a content-length-range condition
    so S3 rejects uploads larger than 10 MB.
    """
    mock_client = _mock_s3_client(FAKE_PRESIGNED_RESPONSE)

    with patch("app.services.storage.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client
        storage.generate_upload_url(
            folder="clubs/logos",
            filename="logo.png",
            content_type="image/png",
        )

    conditions = mock_client.generate_presigned_post.call_args[1]["Conditions"]
    size_conditions = [c for c in conditions if isinstance(c, list)]
    assert len(size_conditions) == 1
    kind, min_size, max_size = size_conditions[0]
    assert kind == "content-length-range"
    assert min_size == 1
    assert max_size == 10 * 1024 * 1024


def test_get_file_url_builds_cloudfront_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    get_file_url should prepend the CloudFront domain to the S3 key.
    """
    monkeypatch.setattr(storage.settings, "cloudfront_domain", "d1abc2.cloudfront.net")

    url = storage.get_file_url("clubs/logos/uuid.jpg")

    assert url == "https://d1abc2.cloudfront.net/clubs/logos/uuid.jpg"


def test_get_file_url_returns_key_when_domain_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    If CLOUDFRONT_DOMAIN is not set (local development), get_file_url
    should return the raw key rather than crashing or returning a broken URL.
    """
    monkeypatch.setattr(storage.settings, "cloudfront_domain", "")

    result = storage.get_file_url("clubs/logos/uuid.jpg")

    assert result == "clubs/logos/uuid.jpg"


def test_delete_file_calls_delete_object() -> None:
    """
    delete_file should call s3.delete_object with the correct bucket and key.
    """
    mock_client = MagicMock()

    with patch("app.services.storage.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client
        storage.delete_file("releases/documents/uuid.pdf")

    mock_client.delete_object.assert_called_once_with(
        Bucket=storage.settings.s3_bucket_name,
        Key="releases/documents/uuid.pdf",
    )


# ---------------------------------------------------------------------------
# Integration tests — upload URL endpoints via TestClient
# ---------------------------------------------------------------------------


def test_club_logo_upload_url_endpoint(client: TestClient, db: Session) -> None:
    """
    POST /clubs/{id}/logo-upload-url/ should return the presigned URL structure.
    Returns 404 if the club does not exist.
    """
    club = Club(name="Wattala SC", code="WSC", status=ClubStatus.ACTIVE)
    db.add(club)
    db.commit()
    db.refresh(club)

    with patch("app.services.storage.boto3") as mock_boto3:
        mock_boto3.client.return_value = _mock_s3_client(FAKE_PRESIGNED_RESPONSE)
        response = client.post(
            f"/clubs/{club.id}/logo-upload-url/",
            params={"filename": "logo.jpg", "content_type": "image/jpeg"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "url" in body
    assert "fields" in body
    assert "key" in body
    assert body["expires_in"] == 900


def test_club_logo_upload_url_404_for_unknown_club(client: TestClient) -> None:
    response = client.post(
        "/clubs/99999/logo-upload-url/",
        params={"filename": "logo.jpg"},
    )
    assert response.status_code == 404


def test_player_photo_upload_url_endpoint(client: TestClient, db: Session) -> None:
    """
    POST /players/{id}/photo-upload-url/ should return the presigned URL structure.
    """
    player = Player(
        league_player_code="WL-0001",
        full_name="Kamal Perera",
        date_of_birth=datetime(1995, 6, 15).date(),
        nic_number="199516500123",
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    with patch("app.services.storage.boto3") as mock_boto3:
        mock_boto3.client.return_value = _mock_s3_client(FAKE_PRESIGNED_RESPONSE)
        response = client.post(
            f"/players/{player.id}/photo-upload-url/",
            params={"filename": "photo.jpg", "content_type": "image/jpeg"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "key" in body
    # key must be scoped to the player's folder
    assert f"players/{player.id}/photos/" in body["key"]


def test_release_document_upload_url_endpoint(client: TestClient) -> None:
    """
    POST /releases/document-upload-url/ does NOT require an existing release.
    The document is uploaded first; the key is submitted with the release.
    """
    with patch("app.services.storage.boto3") as mock_boto3:
        mock_boto3.client.return_value = _mock_s3_client(FAKE_PRESIGNED_RESPONSE)
        response = client.post(
            "/releases/document-upload-url/",
            params={
                "filename": "release-letter.pdf",
                "content_type": "application/pdf",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert "key" in body
    assert body["key"].startswith("releases/documents/")
    assert body["key"].endswith(".pdf")


# ---------------------------------------------------------------------------
# Integration test — release creation stores S3 key (not a URL)
# ---------------------------------------------------------------------------


@pytest.fixture()
def _club(db: Session) -> Club:
    c = Club(name="Wattala SC", code="WSC", status=ClubStatus.ACTIVE)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def _player(db: Session) -> Player:
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
def _active_registration(
    db: Session, _club: Club, _player: Player
) -> PlayerSeasonRegistration:
    season = Season(
        name="2025 Season",
        year=2025,
        registration_open_at=NOW - timedelta(days=1),
        registration_close_at=NOW + timedelta(days=30),
        status=SeasonStatus.OPEN,
        is_locked=False,
    )
    db.add(season)
    db.flush()

    reg = PlayerSeasonRegistration(
        season_id=season.id,
        club_id=_club.id,
        player_id=_player.id,
        registration_type=RegistrationType.NEW,
        status=PlayerSeasonRegistrationStatus.ACTIVE,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


def test_create_release_stores_s3_key_not_url(
    client: TestClient,
    db: Session,
    _active_registration: PlayerSeasonRegistration,
) -> None:
    """
    POST /releases/ should store the S3 object key in the database —
    not a file path and not a full URL.

    The document in the response includes the computed CloudFront URL
    (file_url) AND the raw S3 key (s3_key).
    """
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=999, role="league_admin"
    )

    s3_key = "releases/documents/a1b2c3d4-test.pdf"
    payload = {
        "registration_id": _active_registration.id,
        "s3_key": s3_key,
        "file_name": "release-letter.pdf",
    }
    response = client.post("/releases/", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert len(body["documents"]) == 1

    doc = body["documents"][0]

    # The s3_key in the response must be exactly what we submitted
    assert doc["s3_key"] == s3_key

    # The file_name is the human-readable name, unrelated to the key
    assert doc["file_name"] == "release-letter.pdf"

    # Verify the key is what is stored in the DB
    db.expire_all()
    stored_doc = db.get(ReleaseDocument, doc["id"])
    assert stored_doc is not None
    assert stored_doc.s3_key == s3_key
    # Confirm nothing that looks like a filesystem path is in the key
    assert not stored_doc.s3_key.startswith("/")
    assert not stored_doc.s3_key.startswith("./")
