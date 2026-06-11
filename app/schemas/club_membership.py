from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ClubMembershipRequestRead(BaseModel):
    id: int
    player_id: int
    club_id: int
    requested_by_user_id: int
    status: str
    responded_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClubMembershipRequestCreate(BaseModel):
    player_id: int


class ClubMembershipDecide(BaseModel):
    decision: str  # "accept" | "reject"
