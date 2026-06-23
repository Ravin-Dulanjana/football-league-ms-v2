"""
Demo reset script — wipe everything except the super admin account.

Run this ON the EC2 server to start fresh before running seed_demo.py.

    cd /opt/football-league
    python scripts/reset_demo.py

The script:
  1. Reads .env from the current directory
  2. Connects to the database
  3. Shows what will be deleted
  4. Prompts for the word RESET to confirm
  5. Deletes all Cognito accounts except the super admin
  6. Wipes all DB tables (except league_info and the super admin user row)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------

env_path = Path(".env")
if not env_path.exists():
    print("ERROR: .env not found in the current directory.")
    print("       Run this script from /opt/football-league/")
    sys.exit(1)

for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
AWS_REGION = os.environ.get(
    "COGNITO_REGION", os.environ.get("AWS_REGION", "ap-southeast-1")
)

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Imports (stdlib + packages that are in the venv)
# ---------------------------------------------------------------------------

import boto3  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

# ---------------------------------------------------------------------------
# Step 1 — read the DB and show what will be deleted
# ---------------------------------------------------------------------------

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    rows = conn.execute(
        text(
            "SELECT id, email, role, cognito_sub FROM users"
            " WHERE role != 'super_admin' ORDER BY id"
        )
    ).fetchall()
    season_count = conn.execute(text("SELECT COUNT(*) FROM seasons")).scalar() or 0
    club_count = conn.execute(text("SELECT COUNT(*) FROM clubs")).scalar() or 0

if not rows and not season_count and not club_count:
    print("Nothing to reset — database is already clean.")
    sys.exit(0)

print("\n" + "=" * 60)
print("  WFL DEMO RESET")
print("=" * 60)
if rows:
    print(f"\n  {len(rows)} user(s) will be permanently deleted:\n")
    for row in rows:
        print(f"    [{row.id:>3}]  {row.email:<40}  {row.role}")
else:
    print("\n  No non-super-admin users found.")
if season_count or club_count:
    print(f"\n  Orphaned data: {season_count} season(s), {club_count} club(s)")
print()
print("  All clubs, seasons, players, registrations, releases,")
print("  memberships, notifications, and audit logs will be wiped.")
print("  league_info is preserved.")
print()
print("  The super admin account is NOT affected.")
print("=" * 60)
print()

answer = input("  Type  RESET  to confirm, or anything else to cancel: ").strip()
if answer != "RESET":
    print("\nAborted — nothing was changed.")
    sys.exit(0)

print()

# ---------------------------------------------------------------------------
# Step 2 — delete Cognito accounts
# ---------------------------------------------------------------------------

if not USER_POOL_ID:
    print("WARNING: COGNITO_USER_POOL_ID not set — skipping Cognito deletion.")
    print("         Users will be removed from the DB only.")
    cognito_ok = False
else:
    cognito_ok = True
    idp = boto3.client("cognito-idp", region_name=AWS_REGION)

deleted_cognito = 0
skipped_cognito = 0

for row in rows:
    if not cognito_ok:
        break
    try:
        idp.admin_delete_user(UserPoolId=USER_POOL_ID, Username=row.cognito_sub)
        print(f"  Cognito deleted: {row.email}")
        deleted_cognito += 1
    except idp.exceptions.UserNotFoundException:
        skipped_cognito += 1
    except Exception as exc:
        print(f"  WARNING: Cognito delete failed for {row.email}: {exc}")
        skipped_cognito += 1

if cognito_ok:
    print(
        f"\n  Cognito: {deleted_cognito} deleted, {skipped_cognito} not found/skipped"
    )

# ---------------------------------------------------------------------------
# Step 3 — wipe DB tables
#
# SET session_replication_role = 'replica' disables FK constraint triggers
# for this session, so we can delete in any order without FK violations.
# ---------------------------------------------------------------------------

print("\n  Wiping database tables...")

WIPE_TABLES = [
    "notifications",
    "notification_preferences",
    "player_documents",
    "release_documents",
    "player_releases",
    "club_season_comments",
    "club_staff",
    "club_season_profiles",
    "player_season_registrations",
    "registration_requests",
    "club_membership_requests",
    "user_governance_roles",
    "unlock_approvals",
    "club_unlock_requests",
    "audit_logs",
]

with engine.begin() as conn:
    conn.execute(text("SET session_replication_role = 'replica'"))

    for table in WIPE_TABLES:
        conn.execute(text(f"DELETE FROM {table}"))  # noqa: S608

    # Delete non-super-admin users (their player_id FK to players)
    conn.execute(text("DELETE FROM users WHERE role != 'super_admin'"))

    # Clear super admin's player_id in case it pointed to a player row
    conn.execute(text("UPDATE users SET player_id = NULL WHERE role = 'super_admin'"))

    # Clear players before re-enabling FK constraints
    conn.execute(text("DELETE FROM players"))
    conn.execute(text("DELETE FROM clubs"))
    conn.execute(text("DELETE FROM seasons"))

    conn.execute(text("SET session_replication_role = 'origin'"))

print("  Database wiped.")
print()
print("=" * 60)
print("  Reset complete. Run seed_demo.py to populate demo data.")
print("=" * 60)
print()
