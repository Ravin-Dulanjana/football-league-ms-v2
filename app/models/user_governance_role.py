"""
UserGovernanceRole — junction table for multi-role governance assignments.

A user's base identity (member_type) is separate from governance roles.
A player can simultaneously hold club_admin AND league_admin; this table
records every active governance role so all can be displayed in the UI.

users.role still stores the single highest role for JWT backwards-compat.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserGovernanceRole(Base):
    __tablename__ = "user_governance_roles"
    __table_args__ = (Index("ix_ugr_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    # club_id is required when role=club_admin, null otherwise
    club_id: Mapped[int | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    assigned_by_id: Mapped[int | None] = mapped_column(nullable=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=False, default="")
