from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.club import Club, ClubStatus


def test_list_clubs_empty(client: TestClient) -> None:
    response = client.get("/clubs/")
    assert response.status_code == 200
    assert response.json() == []


def test_list_clubs_returns_active_only(client: TestClient, db: Session) -> None:
    active = Club(name="Wattala SC", code="WSC", status=ClubStatus.ACTIVE)
    inactive = Club(name="Old Town FC", code="OTF", status=ClubStatus.INACTIVE)
    suspended = Club(name="Rough FC", code="RFC", status=ClubStatus.SUSPENDED)
    db.add_all([active, inactive, suspended])
    db.commit()

    response = client.get("/clubs/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Wattala SC"
    assert data[0]["code"] == "WSC"
    assert data[0]["status"] == "active"
