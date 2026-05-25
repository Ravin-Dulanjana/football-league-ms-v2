from __future__ import annotations

from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: int
    role: str  # "admin" | "club_admin" | "player"
    player_id: int | None = None


def get_current_user() -> CurrentUser:
    """
    Placeholder until JWT auth is implemented.
    Override via app.dependency_overrides[get_current_user] in tests.
    """
    return CurrentUser(id=1, role="admin")
