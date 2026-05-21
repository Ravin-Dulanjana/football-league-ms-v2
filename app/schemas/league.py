from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LeagueRead(BaseModel):
    id: int
    name: str
    code: str
    district: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
