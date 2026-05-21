from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.league import League


def test_list_leagues_empty(client: TestClient) -> None:
    response = client.get("/leagues/")
    assert response.status_code == 200
    assert response.json() == []


def test_list_leagues_returns_active_only(client: TestClient, db: Session) -> None:
    active = League(
        name="Wattala League",
        code="wl",
        district="Western Province",
        is_active=True,
    )
    inactive = League(name="Old League", code="ol", is_active=False)
    db.add_all([active, inactive])
    db.commit()

    response = client.get("/leagues/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Wattala League"
    assert data[0]["code"] == "wl"
    assert data[0]["is_active"] is True
