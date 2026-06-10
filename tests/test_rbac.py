"""
Phase 8 RBAC tests — 11 tests covering the role-permission matrix.

Tests 1-11 of the Phase 8 suite.

Each test corresponds directly to a spec requirement.  We use FastAPI's
dependency_overrides to inject different CurrentUser roles without
needing real JWT tokens.

The default conftest `client` fixture uses super_admin.  Tests that need
a different role use the `make_client` helper to create a scoped client.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUser, get_current_user
from app.models.club import Club
from app.models.club_season import (
    ClubSeasonProfile,
    ClubSeasonProfileStatus,
    ClubStaff,
    ClubUnlockRequest,
    UnlockRequestStatus,
)
from app.models.season import Season, SeasonStatus
from main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_client(db: Session, user: CurrentUser) -> TestClient:
    """Create a TestClient that authenticates as the given user."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=True)


def _open_season(db: Session) -> Season:
    """Insert and return an open season with a registration window that is active."""
    now = datetime.now(tz=UTC)
    season = Season(
        name="2026 Season",
        year=2026,
        registration_open_at=now - timedelta(days=1),
        registration_close_at=now + timedelta(days=30),
        status=SeasonStatus.OPEN,
        is_locked=False,
    )
    db.add(season)
    db.commit()
    db.refresh(season)
    return season


def _closed_season(db: Session) -> Season:
    """Insert and return a closed season (window has passed)."""
    now = datetime.now(tz=UTC)
    season = Season(
        name="2025 Season",
        year=2025,
        registration_open_at=now - timedelta(days=60),
        registration_close_at=now - timedelta(days=30),
        status=SeasonStatus.OPEN,
        is_locked=False,
    )
    db.add(season)
    db.commit()
    db.refresh(season)
    return season


def _club(db: Session, name: str = "Test FC", code: str = "TFC") -> Club:
    club = Club(name=name, code=code)
    db.add(club)
    db.commit()
    db.refresh(club)
    return club


# ---------------------------------------------------------------------------
# Test 1: super_admin can access every endpoint
# ---------------------------------------------------------------------------


def test_super_admin_can_list_users(
    client: TestClient,
) -> None:
    """
    super_admin can reach GET /users/.
    The conftest client IS super_admin — just verify it returns 200.
    """
    response = client.get("/users/")
    assert response.status_code == 200, response.text


def test_super_admin_can_list_seasons_without_auth(
    db: Session,
) -> None:
    """
    GET /seasons/ is public — no authentication required.
    We hit it without any user override to confirm it returns 200.
    """
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        response = c.get("/seasons/")
    app.dependency_overrides.clear()
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Test 2: league_admin cannot create super_admin accounts
# ---------------------------------------------------------------------------


def test_league_admin_cannot_create_super_admin_account(
    db: Session,
) -> None:
    """
    league_admin may create any role except super_admin.
    Trying to create a super_admin account must return 400.
    """
    league_admin = CurrentUser(id=10, role="league_admin")
    with make_client(db, league_admin) as c:
        response = c.post(
            "/users/",
            json={
                "email": "newsuperadmin@test.com",
                "role": "super_admin",
                "temporary_password": "Temp1234!",
            },
        )
    assert response.status_code == 400, response.text
    assert "super_admin" in response.json()["detail"].lower()


def test_league_admin_can_create_league_admin_account(
    db: Session,
) -> None:
    """
    league_admin is allowed to create another league_admin account.
    """
    league_admin = CurrentUser(id=10, role="league_admin")
    with make_client(db, league_admin) as c:
        response = c.post(
            "/users/",
            json={
                "email": "newleagueadmin@test.com",
                "role": "league_admin",
                "temporary_password": "Temp1234!",
            },
        )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "league_admin"


def test_league_admin_can_create_club_admin_account(
    db: Session,
) -> None:
    """
    league_admin IS allowed to create club_admin accounts.
    Should return 201 (Cognito call is skipped in dev mode when
    cognito_user_pool_id is empty).
    """
    club = _club(db)
    league_admin = CurrentUser(id=10, role="league_admin")
    with make_client(db, league_admin) as c:
        response = c.post(
            "/users/",
            json={
                "email": "newclubadmin@test.com",
                "role": "club_admin",
                "club_id": club.id,
                "temporary_password": "Temp1234!",
            },
        )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "club_admin"


# ---------------------------------------------------------------------------
# Test 3: league_admin cannot manage super_admin accounts
# ---------------------------------------------------------------------------


def test_league_admin_cannot_deactivate_super_admin(
    db: Session,
) -> None:
    """
    POST /users/{id}/account-action/ with action=deactivate must return 403
    when the actor is league_admin and the target is super_admin.
    """
    # Create a super_admin user record
    from app.models.user import User  # noqa: PLC0415

    target = User(
        cognito_sub="super-sub-1",
        email="superadmin@test.com",
        role="super_admin",
    )
    db.add(target)
    db.commit()
    db.refresh(target)

    league_admin = CurrentUser(id=99, role="league_admin")
    with make_client(db, league_admin) as c:
        response = c.post(
            f"/users/{target.id}/account-action/",
            json={"action": "deactivate", "reason": "Testing"},
        )
    assert response.status_code == 403, response.text
    assert "league admin" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 4: club_admin can only submit their own club's profile
# ---------------------------------------------------------------------------


def test_club_admin_cannot_submit_another_clubs_profile(
    db: Session,
) -> None:
    """
    A club_admin for club 1 must get 403 when trying to submit club 2's profile.
    """
    club1 = _club(db, "Club One", "C1")
    club2 = _club(db, "Club Two", "C2")
    season = _open_season(db)

    profile = ClubSeasonProfile(
        club_id=club2.id,
        season_id=season.id,
        status=ClubSeasonProfileStatus.DRAFT,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    club1_admin = CurrentUser(id=5, role="club_admin", club_id=club1.id)
    with make_client(db, club1_admin) as c:
        response = c.post(f"/club-season-profiles/{profile.id}/submit/")
    assert response.status_code == 403, response.text


def test_club_admin_can_submit_own_clubs_profile(
    db: Session,
) -> None:
    """
    A club_admin for club 1 CAN submit their own club's profile.
    """
    club = _club(db, "My Club", "MC")
    season = _open_season(db)

    profile = ClubSeasonProfile(
        club_id=club.id,
        season_id=season.id,
        status=ClubSeasonProfileStatus.DRAFT,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    club_admin = CurrentUser(id=5, role="club_admin", club_id=club.id)
    with make_client(db, club_admin) as c:
        response = c.post(f"/club-season-profiles/{profile.id}/submit/")
    assert response.status_code == 200, response.text
    assert response.json()["status"] in ("submitted", "resubmitted")


# ---------------------------------------------------------------------------
# Test 5: club_admin cannot see internal comments
# ---------------------------------------------------------------------------


def test_club_admin_cannot_see_internal_comments(
    db: Session,
) -> None:
    """
    GET /club-season-profiles/{id}/comments/ for a club_admin must NOT
    return comments where is_internal=True.
    """
    from app.models.club_season import ClubSeasonComment  # noqa: PLC0415

    club = _club(db)
    season = _open_season(db)

    profile = ClubSeasonProfile(
        club_id=club.id, season_id=season.id, status=ClubSeasonProfileStatus.SUBMITTED
    )
    db.add(profile)
    db.flush()

    external = ClubSeasonComment(
        profile_id=profile.id, author_id=1, content="External note", is_internal=False
    )
    internal = ClubSeasonComment(
        profile_id=profile.id,
        author_id=1,
        content="Internal note — do not share",
        is_internal=True,
    )
    db.add_all([external, internal])
    db.commit()
    db.refresh(profile)

    club_admin = CurrentUser(id=5, role="club_admin", club_id=club.id)
    with make_client(db, club_admin) as c:
        response = c.get(f"/club-season-profiles/{profile.id}/comments/")

    assert response.status_code == 200
    comments = response.json()
    texts = [c["content"] for c in comments]
    assert "External note" in texts
    assert "Internal note — do not share" not in texts


# ---------------------------------------------------------------------------
# Test 6: player can only decide their own registration request
# ---------------------------------------------------------------------------


def test_player_cannot_decide_another_players_registration(
    client: TestClient, db: Session
) -> None:
    """
    POST /registration-requests/{id}/decide/ with a player user whose
    player_id doesn't match the request's player_id must return 403.
    Re-verified here as part of the Phase 8 spec audit.
    """
    from app.models.player import Player  # noqa: PLC0415
    from app.models.registration import (  # noqa: PLC0415
        RegistrationRequest,
        RegistrationRequestStatus,
    )

    club = _club(db, "Player Test FC", "PTFC")
    season = _open_season(db)

    player1 = Player(
        league_player_code="P001",
        full_name="Player One",
        date_of_birth=date(1995, 1, 1),
        nic_number="NIC001",
    )
    player2 = Player(
        league_player_code="P002",
        full_name="Player Two",
        date_of_birth=date(1996, 1, 1),
        nic_number="NIC002",
    )
    db.add_all([player1, player2])
    db.flush()

    req = RegistrationRequest(
        season_id=season.id,
        club_id=club.id,
        player_id=player1.id,
        requested_by_user_id=1,
        status=RegistrationRequestStatus.PENDING_PLAYER_CONFIRMATION,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    # player2 tries to decide player1's request
    player2_user = CurrentUser(id=20, role="player", player_id=player2.id)
    with make_client(db, player2_user) as c:
        response = c.post(
            f"/registration-requests/{req.id}/decide/",
            json={"decision": "accept"},
        )
    assert response.status_code == 403, response.text


# ---------------------------------------------------------------------------
# Test 7: club staff max 6 per club per season is enforced
# ---------------------------------------------------------------------------


def test_club_staff_max_6_enforced(
    db: Session,
) -> None:
    """
    POST /club-staff/ must return 400 when a club already has 6 staff for
    the season.
    """
    club = _club(db, "Staff FC", "SFC")
    season = _open_season(db)

    # Add 6 staff directly via ORM
    for i in range(6):
        staff = ClubStaff(
            club_id=club.id,
            season_id=season.id,
            full_name=f"Staff Member {i}",
            role="coach",
        )
        db.add(staff)
    db.commit()

    super_admin = CurrentUser(id=1, role="super_admin")
    with make_client(db, super_admin) as c:
        response = c.post(
            "/club-staff/",
            json={
                "club_id": club.id,
                "season_id": season.id,
                "full_name": "Seventh Staff",
                "role": "physio",
            },
        )
    assert response.status_code == 400, response.text
    assert "maximum" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 8: season status transition draft → archived directly is rejected
# ---------------------------------------------------------------------------


def test_season_cannot_jump_from_draft_to_archived(
    client: TestClient, db: Session
) -> None:
    """
    PATCH /seasons/{id}/ with status=archived when current status=draft
    must return 400.  Only draft→open is valid.
    """
    now = datetime.now(tz=UTC)
    season = Season(
        name="2027 Season",
        year=2027,
        registration_open_at=now + timedelta(days=1),
        registration_close_at=now + timedelta(days=30),
        status=SeasonStatus.DRAFT,
    )
    db.add(season)
    db.commit()
    db.refresh(season)

    response = client.patch(
        f"/seasons/{season.id}/",
        json={"status": "archived"},
    )
    assert response.status_code == 400, response.text
    assert "archived" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 9: club unlock requires 2 separate approvals
# ---------------------------------------------------------------------------


def test_club_unlock_requires_two_approvals(
    db: Session,
) -> None:
    """
    A club unlock request only becomes APPROVED after 2 distinct
    league_admin accounts approve it.

    After 1 approval it must still be PENDING.
    After a second approval by a different admin it must be APPROVED.
    """
    club = _club(db, "Unlock FC", "UFC")
    season = _closed_season(db)

    req = ClubUnlockRequest(
        club_id=club.id,
        season_id=season.id,
        requested_by=10,  # club_admin user
        reason="Need to add late transfer",
        status=UnlockRequestStatus.PENDING,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    admin1 = CurrentUser(id=11, role="league_admin")
    admin2 = CurrentUser(id=12, role="league_admin")

    # First approval — still pending
    with make_client(db, admin1) as c:
        r1 = c.post(
            f"/club-unlock-requests/{req.id}/decide/",
            json={"decision": "approve"},
        )
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "pending"
    assert r1.json()["approval_count"] == 1

    # Second approval by a different admin — now approved
    with make_client(db, admin2) as c:
        r2 = c.post(
            f"/club-unlock-requests/{req.id}/decide/",
            json={"decision": "approve"},
        )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "approved"
    assert r2.json()["approval_count"] == 2


# ---------------------------------------------------------------------------
# Test 10: public endpoints return data without auth token
# ---------------------------------------------------------------------------


def test_get_seasons_requires_no_auth(
    db: Session,
) -> None:
    """
    GET /seasons/ must return 200 with no Authorization header.
    No dependency override for get_current_user.
    """
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        response = c.get("/seasons/")
    app.dependency_overrides.clear()
    assert response.status_code == 200


def test_get_clubs_still_requires_auth(
    db: Session,
) -> None:
    """
    GET /clubs/ is NOT public (per existing spec) — requires auth.
    Confirms that making /seasons/ public didn't accidentally break /clubs/.
    """
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        response = c.get("/clubs/")
    app.dependency_overrides.clear()
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test 11: audit log written for account action
# ---------------------------------------------------------------------------


def test_audit_log_written_for_deactivate_action(
    db: Session,
) -> None:
    """
    POST /users/{id}/account-action/ with action=deactivate must create
    exactly one AuditLog row with action="user.deactivate".
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.audit_log import AuditLog  # noqa: PLC0415
    from app.models.user import User  # noqa: PLC0415

    target = User(
        cognito_sub="target-sub-1",
        email="target@test.com",
        role="club_admin",
    )
    db.add(target)
    db.commit()
    db.refresh(target)

    # Use id=999 so it doesn't collide with the target user's auto-assigned PK
    super_admin = CurrentUser(id=999, role="super_admin")
    with make_client(db, super_admin) as c:
        response = c.post(
            f"/users/{target.id}/account-action/",
            json={"action": "deactivate", "reason": "Disciplinary action"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False

    logs = (
        db.execute(
            select(AuditLog).where(
                AuditLog.action == "user.deactivate",
                AuditLog.entity_id == target.id,
            )
        )
        .scalars()
        .all()
    )

    assert len(logs) == 1
    assert logs[0].actor_id == super_admin.id
    assert logs[0].details is not None
    details = json.loads(logs[0].details)
    assert "reason" in details


# ---------------------------------------------------------------------------
# Tests 12–19: AuditLog and notification coverage (gap fill)
# ---------------------------------------------------------------------------


def test_season_create_writes_audit_log(db: Session) -> None:
    """
    Test 12: POST /seasons/ must write an AuditLog row with action='season.create'.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.audit_log import AuditLog  # noqa: PLC0415

    league_admin = CurrentUser(id=50, role="league_admin")
    with make_client(db, league_admin) as c:
        response = c.post(
            "/seasons/",
            json={
                "name": "Audit Test Season",
                "year": 2030,
                "registration_open_at": "2030-01-01T00:00:00Z",
                "registration_close_at": "2030-06-30T00:00:00Z",
            },
        )
    assert response.status_code == 201, response.text
    season_id = response.json()["id"]

    logs = (
        db.execute(
            select(AuditLog).where(
                AuditLog.action == "season.create",
                AuditLog.entity_id == season_id,
            )
        )
        .scalars()
        .all()
    )
    assert len(logs) == 1
    assert logs[0].actor_id == league_admin.id


def test_season_create_notifies_club_admins(db: Session) -> None:
    """
    Test 13: POST /seasons/ must create Notification rows for every active club_admin.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.notification import Notification  # noqa: PLC0415
    from app.models.user import User  # noqa: PLC0415

    # Create two club_admin users so we can assert both are notified
    club_admin_a = User(
        cognito_sub="ca-notify-a",
        email="ca-notify-a@test.com",
        role="club_admin",
        is_active=True,
        is_deleted=False,
    )
    club_admin_b = User(
        cognito_sub="ca-notify-b",
        email="ca-notify-b@test.com",
        role="club_admin",
        is_active=True,
        is_deleted=False,
    )
    db.add_all([club_admin_a, club_admin_b])
    db.commit()
    db.refresh(club_admin_a)
    db.refresh(club_admin_b)

    super_admin = CurrentUser(id=999, role="super_admin")
    with make_client(db, super_admin) as c:
        response = c.post(
            "/seasons/",
            json={
                "name": "Notification Test Season",
                "year": 2031,
                "registration_open_at": "2031-01-01T00:00:00Z",
                "registration_close_at": "2031-06-30T00:00:00Z",
            },
        )
    assert response.status_code == 201, response.text

    # Both club_admin users should have received a notification
    for uid in (club_admin_a.id, club_admin_b.id):
        notif = db.execute(
            select(Notification).where(
                Notification.user_id == uid,
                Notification.event_type == "season.created",
            )
        ).scalar_one_or_none()
        assert notif is not None, f"No notification for club_admin id={uid}"


def test_season_status_change_writes_audit_and_notifies(db: Session) -> None:
    """
    Test 14: PATCH /seasons/{id}/ with a status change must write AuditLog
    AND create Notification rows for club_admins.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.audit_log import AuditLog  # noqa: PLC0415
    from app.models.notification import Notification  # noqa: PLC0415
    from app.models.user import User  # noqa: PLC0415

    # Plant a club_admin to receive the notification
    watcher = User(
        cognito_sub="ca-status-watcher",
        email="watcher@test.com",
        role="club_admin",
        is_active=True,
        is_deleted=False,
    )
    db.add(watcher)
    db.commit()
    db.refresh(watcher)

    # Create a draft season directly in DB (bypasses the service, avoids audit noise)
    draft_season = Season(
        name="Status Change Season",
        year=2032,
        registration_open_at=datetime.now(tz=UTC) + timedelta(days=1),
        registration_close_at=datetime.now(tz=UTC) + timedelta(days=60),
        status=SeasonStatus.DRAFT,
        is_locked=False,
    )
    db.add(draft_season)
    db.commit()
    db.refresh(draft_season)

    super_admin = CurrentUser(id=999, role="super_admin")
    with make_client(db, super_admin) as c:
        response = c.patch(
            f"/seasons/{draft_season.id}/",
            json={"status": "open"},
        )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "open"

    # Audit log written
    log = db.execute(
        select(AuditLog).where(
            AuditLog.action == "season.update",
            AuditLog.entity_id == draft_season.id,
        )
    ).scalar_one_or_none()
    assert log is not None
    assert log.actor_id == super_admin.id

    # Notification sent to the club_admin
    notif = db.execute(
        select(Notification).where(
            Notification.user_id == watcher.id,
            Notification.event_type == "season.status_changed",
        )
    ).scalar_one_or_none()
    assert notif is not None


def test_profile_submit_notifies_league_admins(db: Session) -> None:
    """
    Test 15: Submitting a club season profile must create Notification rows
    for all league_admins.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.notification import Notification  # noqa: PLC0415
    from app.models.user import User  # noqa: PLC0415

    season = _open_season(db)
    club = _club(db, "Submit Notif Club", "SNC")

    # Plant a league_admin to receive the notification
    la = User(
        cognito_sub="la-submit-notif",
        email="la-submit@test.com",
        role="league_admin",
        is_active=True,
        is_deleted=False,
    )
    db.add(la)
    db.commit()
    db.refresh(la)

    # Create profile directly in DB
    profile = ClubSeasonProfile(
        club_id=club.id,
        season_id=season.id,
        status=ClubSeasonProfileStatus.DRAFT,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    club_admin = CurrentUser(id=5, role="club_admin", club_id=club.id)
    with make_client(db, club_admin) as c:
        response = c.post(f"/club-season-profiles/{profile.id}/submit/")

    assert response.status_code == 200, response.text

    notif = db.execute(
        select(Notification).where(
            Notification.user_id == la.id,
            Notification.event_type == "club_profile.submitted",
        )
    ).scalar_one_or_none()
    assert notif is not None


def test_profile_transition_notifies_club_admin(db: Session) -> None:
    """
    Test 16: Transitioning a club season profile must notify the club's
    own club_admin(s).
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.notification import Notification  # noqa: PLC0415
    from app.models.user import User  # noqa: PLC0415

    season = _open_season(db)
    club = _club(db, "Transition Notif Club", "TNC")

    # Plant a club_admin for this specific club
    ca = User(
        cognito_sub="ca-transition-notif",
        email="ca-transition@test.com",
        role="club_admin",
        club_id=club.id,
        is_active=True,
        is_deleted=False,
    )
    db.add(ca)
    db.commit()
    db.refresh(ca)

    profile = ClubSeasonProfile(
        club_id=club.id,
        season_id=season.id,
        status=ClubSeasonProfileStatus.SUBMITTED,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    super_admin = CurrentUser(id=999, role="super_admin")
    with make_client(db, super_admin) as c:
        response = c.post(
            f"/club-season-profiles/{profile.id}/transition/",
            json={"target_status": "reviewed"},
        )

    assert response.status_code == 200, response.text

    notif = db.execute(
        select(Notification).where(
            Notification.user_id == ca.id,
            Notification.event_type == "club_profile.transitioned",
        )
    ).scalar_one_or_none()
    assert notif is not None


def test_registration_request_create_writes_audit_log(db: Session) -> None:
    """
    Test 17: POST /registration-requests/ must write an AuditLog row.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.audit_log import AuditLog  # noqa: PLC0415
    from app.models.player import Player  # noqa: PLC0415

    season = _open_season(db)
    club = _club(db, "Reg Audit Club", "RAC")
    player = Player(
        league_player_code="P-AUDIT-001",
        full_name="Audit Player",
        date_of_birth=date(1998, 5, 10),
        nic_number="NIC-AUDIT-001",
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    club_admin = CurrentUser(id=5, role="club_admin", club_id=club.id)
    with make_client(db, club_admin) as c:
        response = c.post(
            "/registration-requests/",
            json={
                "player_id": player.id,
                "season_id": season.id,
                "club_id": club.id,
            },
        )
    assert response.status_code == 201, response.text
    req_id = response.json()["id"]

    log = db.execute(
        select(AuditLog).where(
            AuditLog.action == "registration_request.create",
            AuditLog.entity_id == req_id,
        )
    ).scalar_one_or_none()
    assert log is not None
    assert log.actor_id == club_admin.id


def test_release_create_writes_audit_log(db: Session) -> None:
    """
    Test 18: POST /releases/ must write an AuditLog row with action='release.create'.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.audit_log import AuditLog  # noqa: PLC0415
    from app.models.player import Player  # noqa: PLC0415
    from app.models.registration import (  # noqa: PLC0415
        PlayerSeasonRegistration,
        PlayerSeasonRegistrationStatus,
        RegistrationType,
    )

    season = _open_season(db)
    club = _club(db, "Release Audit Club", "RAUC")
    player = Player(
        league_player_code="P-RELEASE-001",
        full_name="Release Audit Player",
        date_of_birth=date(1996, 3, 20),
        nic_number="NIC-RELEASE-001",
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    reg = PlayerSeasonRegistration(
        season_id=season.id,
        club_id=club.id,
        player_id=player.id,
        registration_type=RegistrationType.NEW,
        status=PlayerSeasonRegistrationStatus.ACTIVE,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    club_admin = CurrentUser(id=5, role="club_admin", club_id=club.id)
    with make_client(db, club_admin) as c:
        response = c.post(
            "/releases/",
            json={
                "registration_id": reg.id,
                "s3_key": "releases/documents/test-release.pdf",
                "file_name": "test-release.pdf",
                "effective_date": "2030-06-01",
            },
        )
    assert response.status_code == 201, response.text
    release_id = response.json()["id"]

    log = db.execute(
        select(AuditLog).where(
            AuditLog.action == "release.create",
            AuditLog.entity_id == release_id,
        )
    ).scalar_one_or_none()
    assert log is not None
    assert log.actor_id == club_admin.id


def test_invalid_season_status_transition_rejected(db: Session) -> None:
    """
    Test 19: PATCH /seasons/{id}/ with an invalid status jump (draft→archived)
    must return 400.  This is a direct re-test of the VALID_TRANSITIONS guard
    now that the route captures current_user properly.
    """
    draft_season = Season(
        name="Invalid Transition Season",
        year=2033,
        registration_open_at=datetime.now(tz=UTC) + timedelta(days=1),
        registration_close_at=datetime.now(tz=UTC) + timedelta(days=60),
        status=SeasonStatus.DRAFT,
        is_locked=False,
    )
    db.add(draft_season)
    db.commit()
    db.refresh(draft_season)

    super_admin = CurrentUser(id=999, role="super_admin")
    with make_client(db, super_admin) as c:
        response = c.patch(
            f"/seasons/{draft_season.id}/",
            json={"status": "archived"},
        )
    assert response.status_code == 400, response.text
    assert "Cannot transition" in response.json()["detail"]
