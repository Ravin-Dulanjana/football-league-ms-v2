"""
Reporting and analytics service.

GET /reports/export/ — CSV export scoped by role.
GET /analytics/summary/ — numeric summary scoped by role.

PDF export is explicitly NOT implemented in Phase 8 — it requires a library
dependency (reportlab or weasyprint) not yet in pyproject.toml.  The endpoint
returns 501 if format=pdf is requested.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser
from app.models.club import Club
from app.models.player import Player
from app.models.registration import (
    PlayerSeasonRegistration,
    PlayerSeasonRegistrationStatus,
)
from app.models.release import PlayerRelease, ReleaseStatus
from app.models.season import Season


def export_csv(
    db: Session,
    report_type: str,
    current_user: CurrentUser,
    season_id: int | None = None,
) -> str:
    """
    Generate a CSV string for the requested report_type.

    Scoping:
      super_admin / league_admin — full data
      club_admin                 — only their club's data
    """
    if report_type == "season_rosters":
        return _season_rosters_csv(db, current_user, season_id)
    if report_type == "release_history":
        return _release_history_csv(db, current_user)
    if report_type == "club_staff":
        # club_staff model is available but kept simple here
        return _club_staff_csv(db, current_user, season_id)
    raise ValueError(f"Unknown report_type: {report_type}")


def get_analytics_summary(
    db: Session,
    current_user: CurrentUser,
) -> dict:
    """
    Return a summary dict.  Scoped by role (club_admin only sees their club).
    """
    club_filter = current_user.club_id if current_user.role == "club_admin" else None

    # Total active registrations
    reg_q = select(func.count()).where(
        PlayerSeasonRegistration.status == PlayerSeasonRegistrationStatus.ACTIVE
    )
    if club_filter:
        reg_q = reg_q.where(PlayerSeasonRegistration.club_id == club_filter)
    total_active_players = db.execute(reg_q).scalar_one()

    # Pending registrations
    from app.models.registration import (  # noqa: PLC0415
        RegistrationRequest,
        RegistrationRequestStatus,
    )

    pend_q = select(func.count()).where(
        RegistrationRequest.status
        == RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION
    )
    if club_filter:
        pend_q = pend_q.where(RegistrationRequest.club_id == club_filter)
    pending_registrations = db.execute(pend_q).scalar_one()

    # Pending releases
    rel_q = select(func.count()).where(
        PlayerRelease.status == ReleaseStatus.PENDING_PLAYER_CONFIRMATION
    )
    if club_filter:
        rel_q = rel_q.where(PlayerRelease.from_club_id == club_filter)
    pending_releases = db.execute(rel_q).scalar_one()

    # Season count
    total_seasons = db.execute(select(func.count()).select_from(Season)).scalar_one()
    total_clubs = db.execute(select(func.count()).select_from(Club)).scalar_one()
    total_players = db.execute(select(func.count()).select_from(Player)).scalar_one()

    return {
        "total_active_players": total_active_players,
        "pending_registrations": pending_registrations,
        "pending_releases": pending_releases,
        "total_seasons": total_seasons,
        "total_clubs": total_clubs,
        "total_players": total_players,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "scope": (f"club_id={current_user.club_id}" if club_filter else "all"),
    }


# ---------------------------------------------------------------------------
# CSV builders
# ---------------------------------------------------------------------------


def _season_rosters_csv(
    db: Session, current_user: CurrentUser, season_id: int | None
) -> str:
    q = (
        select(
            PlayerSeasonRegistration,
            Player.full_name,
            Club.name.label("club_name"),
            Season.name.label("season_name"),
        )
        .join(Player, PlayerSeasonRegistration.player_id == Player.id)
        .join(Club, PlayerSeasonRegistration.club_id == Club.id)
        .join(Season, PlayerSeasonRegistration.season_id == Season.id)
        .where(PlayerSeasonRegistration.status == PlayerSeasonRegistrationStatus.ACTIVE)
    )
    if current_user.role == "club_admin":
        q = q.where(PlayerSeasonRegistration.club_id == current_user.club_id)
    if season_id:
        q = q.where(PlayerSeasonRegistration.season_id == season_id)

    rows = db.execute(q).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "registration_id",
            "player_name",
            "club_name",
            "season_name",
            "type",
            "status",
            "registered_at",
        ]
    )
    for reg, player_name, club_name, season_name in rows:
        writer.writerow(
            [
                reg.id,
                player_name,
                club_name,
                season_name,
                reg.registration_type,
                reg.status,
                reg.registered_at.isoformat() if reg.registered_at else "",
            ]
        )
    return buf.getvalue()


def _release_history_csv(db: Session, current_user: CurrentUser) -> str:
    q = (
        select(PlayerRelease, Player.full_name, Club.name.label("from_club"))
        .join(Player, PlayerRelease.player_id == Player.id)
        .join(Club, PlayerRelease.from_club_id == Club.id)
    )
    if current_user.role == "club_admin":
        q = q.where(PlayerRelease.from_club_id == current_user.club_id)

    rows = db.execute(q).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "release_id",
            "player_name",
            "from_club",
            "status",
            "effective_date",
            "confirmed_at",
            "created_at",
        ]
    )
    for rel, player_name, from_club in rows:
        writer.writerow(
            [
                rel.id,
                player_name,
                from_club,
                rel.status,
                rel.effective_date or "",
                rel.confirmed_at.isoformat() if rel.confirmed_at else "",
                rel.created_at.isoformat(),
            ]
        )
    return buf.getvalue()


def _club_staff_csv(
    db: Session, current_user: CurrentUser, season_id: int | None
) -> str:
    from app.models.club_season import ClubStaff  # noqa: PLC0415

    q = select(ClubStaff, Club.name.label("club_name")).join(
        Club, ClubStaff.club_id == Club.id
    )
    if current_user.role == "club_admin":
        q = q.where(ClubStaff.club_id == current_user.club_id)
    if season_id:
        q = q.where(ClubStaff.season_id == season_id)

    rows = db.execute(q).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["staff_id", "full_name", "role", "club_name", "season_id", "created_at"]
    )
    for staff, club_name in rows:
        writer.writerow(
            [
                staff.id,
                staff.full_name,
                staff.role,
                club_name,
                staff.season_id,
                staff.created_at.isoformat(),
            ]
        )
    return buf.getvalue()
