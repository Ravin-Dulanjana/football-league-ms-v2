"""
Demo seed script — creates a fully populated WFL demo environment.

Run from your local machine (or EC2) pointing at the live API:

    python scripts/seed_demo.py \\
        --api http://3.1.116.7 \\
        --email your@superadmin.email \\
        --password "YourSuperAdminPassword"

Dry-run (shows what will be created, no requests made):

    python scripts/seed_demo.py --dry-run

What gets created
-----------------
  Seasons     : WFL Premier 2024 (archived), WFL Premier 2025 (open)
  Clubs       : Wattala Warriors FC, Peliyagoda United, Hendala Rangers
  League admin: 1 user  (asanka@demo.lk)
  Club admins : 3 users — one per club
  Players     : 4 per club = 12 registered players
  Free players: 2 players with no club (for invite demos)
  Total users : 18 non-super-admin accounts

All demo accounts use password: Demo@2026!

Flow
----
  1. Creates all seasons, clubs, users
  2. Completes the force-password-change for every created user
  3. Club admins invite their players → players accept
  4. Club admins send squad registration requests for 2025 → players acknowledge
  5. Prints a summary credentials table
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

TEMP_PASSWORD = "Temp@2026!"  # used on account creation
DEMO_PASSWORD = "Demo@2026!"  # permanent password after first-login challenge

# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

CLUBS = [
    {
        "name": "Wattala Warriors FC",
        "short_name": "WWF",
        "code": "WWF",
        "email": "warriors@wfl.lk",
    },
    {
        "name": "Peliyagoda United",
        "short_name": "PLU",
        "code": "PLU",
        "email": "united@wfl.lk",
    },
    {
        "name": "Hendala Rangers",
        "short_name": "HRG",
        "code": "HRG",
        "email": "rangers@wfl.lk",
    },
]

LEAGUE_ADMIN = {
    "full_name": "Asanka Rathnayake",
    "date_of_birth": "1985-06-15",
    "nic_number": "852670350V",
    "email": "asanka@demo.lk",
    "role": "league_admin",
}

# club_index matches CLUBS list above
CLUB_ADMINS = [
    {
        "full_name": "Nimal Perera",
        "date_of_birth": "1990-03-12",
        "nic_number": "901720150V",
        "email": "nimal.perera@demo.lk",
        "role": "club_admin",
        "club_index": 0,
    },
    {
        "full_name": "Chaminda Silva",
        "date_of_birth": "1988-07-25",
        "nic_number": "882070250V",
        "email": "chaminda.silva@demo.lk",
        "role": "club_admin",
        "club_index": 1,
    },
    {
        "full_name": "Thilak Fernando",
        "date_of_birth": "1992-11-08",
        "nic_number": "923130450V",
        "email": "thilak.fernando@demo.lk",
        "role": "club_admin",
        "club_index": 2,
    },
]

# 4 players per club — same order as CLUBS
PLAYERS_BY_CLUB = [
    [  # Wattala Warriors FC
        {
            "full_name": "Kasun Jayawardena",
            "date_of_birth": "1998-03-14",
            "nic_number": "982730160V",
            "email": "kasun.j@demo.lk",
        },
        {
            "full_name": "Ruwan Bandara",
            "date_of_birth": "2000-07-22",
            "nic_number": "200720360V",
            "email": "ruwan.b@demo.lk",
        },
        {
            "full_name": "Dilshan Herath",
            "date_of_birth": "1997-11-05",
            "nic_number": "973095830V",
            "email": "dilshan.h@demo.lk",
        },
        {
            "full_name": "Banusha Gunasekara",
            "date_of_birth": "2001-01-30",
            "nic_number": "200103090V",
            "email": "banusha.g@demo.lk",
        },
    ],
    [  # Peliyagoda United
        {
            "full_name": "Roshan Kumara",
            "date_of_birth": "1999-06-18",
            "nic_number": "991700420V",
            "email": "roshan.k@demo.lk",
        },
        {
            "full_name": "Gayan Madushanka",
            "date_of_birth": "1996-09-12",
            "nic_number": "962561240V",
            "email": "gayan.m@demo.lk",
        },
        {
            "full_name": "Priyantha Senanayake",
            "date_of_birth": "2002-04-03",
            "nic_number": "202093790V",
            "email": "priyantha.s@demo.lk",
        },
        {
            "full_name": "Chamara Jayawardena",
            "date_of_birth": "1995-12-25",
            "nic_number": "953600520V",
            "email": "chamara.j@demo.lk",
        },
    ],
    [  # Hendala Rangers
        {
            "full_name": "Udara Pathirana",
            "date_of_birth": "1998-08-07",
            "nic_number": "982201860V",
            "email": "udara.p@demo.lk",
        },
        {
            "full_name": "Akila Dananjaya",
            "date_of_birth": "2003-02-14",
            "nic_number": "203450930V",
            "email": "akila.d@demo.lk",
        },
        {
            "full_name": "Chanaka Liyanage",
            "date_of_birth": "1997-05-29",
            "nic_number": "971500490V",
            "email": "chanaka.l@demo.lk",
        },
        {
            "full_name": "Jeewa Mendis",
            "date_of_birth": "2001-10-11",
            "nic_number": "201851230V",
            "email": "jeewa.m@demo.lk",
        },
    ],
]

FREE_PLAYERS = [
    {
        "full_name": "Nadeeka Prasad",
        "date_of_birth": "2002-09-15",
        "nic_number": "202591530V",
        "email": "nadeeka.p@demo.lk",
    },
    {
        "full_name": "Tilan Samaraweera",
        "date_of_birth": "1995-06-07",
        "nic_number": "951590030V",
        "email": "tilan.s@demo.lk",
    },
]

# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no extra deps needed)
# ---------------------------------------------------------------------------


def _raw_request(
    method: str,
    url: str,
    body: dict | None = None,
    token: str | None = None,
) -> tuple[int, Any]:
    """Return (status_code, parsed_json_or_None)."""
    data = json.dumps(body).encode() if body else None
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {url}\n{body_text}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Connection error {method} {url}: {exc.reason}") from exc


def api(
    method: str,
    base: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
) -> Any:
    _, result = _raw_request(method, f"{base}{path}", body, token)
    return result


def get(base: str, path: str, token: str) -> Any:
    return api("GET", base, path, token=token)


def post(base: str, path: str, body: dict, token: str | None = None) -> Any:
    return api("POST", base, path, body, token)


def patch(base: str, path: str, body: dict, token: str) -> Any:
    return api("PATCH", base, path, body, token)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def login(base: str, email: str, password: str) -> str:
    """Login and return id_token. Raises on failure."""
    result = post(base, "/auth/login", {"email": email, "password": password})
    if "id_token" in result:
        return str(result["id_token"])
    raise RuntimeError(f"Unexpected login response: {result}")


def first_login_set_password(base: str, email: str, temp_pw: str, new_pw: str) -> str:
    """Complete the NEW_PASSWORD_REQUIRED challenge. Returns id_token."""
    result = post(base, "/auth/login", {"email": email, "password": temp_pw})
    if result.get("challenge") == "NEW_PASSWORD_REQUIRED":
        result = post(
            base,
            "/auth/complete-challenge",
            {
                "email": email,
                "new_password": new_pw,
                "session": result["session"],
            },
        )
        return str(result["id_token"])
    if "id_token" in result:
        # Challenge was already completed (e.g. re-running the script)
        return str(result["id_token"])
    raise RuntimeError(f"Unexpected login response for {email}: {result}")


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def dry_run() -> None:
    total = (
        1 + len(CLUB_ADMINS) + sum(len(p) for p in PLAYERS_BY_CLUB) + len(FREE_PLAYERS)
    )
    print("\n[DRY RUN] Would create:\n")
    print("  Seasons      : WFL Premier 2024 (archived), WFL Premier 2025 (open)")
    print(f"  Clubs        : {', '.join(c['name'] for c in CLUBS)}")
    print(f"  League admin : {LEAGUE_ADMIN['full_name']} ({LEAGUE_ADMIN['email']})")
    for ca in CLUB_ADMINS:
        club_name = CLUBS[ca["club_index"]]["name"]  # type: ignore[call-overload]
        print(f"  Club admin   : {ca['full_name']} ({ca['email']}) → {club_name}")
    for i, players in enumerate(PLAYERS_BY_CLUB):
        names = ", ".join(p["full_name"] for p in players)
        print(f"  Players      : {names} → {CLUBS[i]['name']}")
    for fp in FREE_PLAYERS:
        print(f"  Free player  : {fp['full_name']} ({fp['email']}) — no club")
    print(f"\n  Total new accounts : {total}")
    print(f"  Demo password for all : {DEMO_PASSWORD}")
    print()


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------


def seed(base: str, admin_email: str, admin_password: str) -> None:  # noqa: C901
    sep = "─" * 56

    # ── 1. Super admin login ────────────────────────────────────
    print(f"\n{sep}")
    print("  Logging in as super admin...")
    admin_token = login(base, admin_email, admin_password)
    print("  OK\n")

    # ── 2. Seasons ──────────────────────────────────────────────
    print(f"{sep}\n  Creating seasons...")

    season_2024 = post(
        base,
        "/seasons/",
        {
            "name": "WFL Premier 2024",
            "year": 2024,
            "registration_open_at": "2024-01-01T00:00:00+00:00",
            "registration_close_at": "2024-03-31T23:59:59+00:00",
            "season_end_date": "2024-12-31T23:59:59+00:00",
        },
        admin_token,
    )
    print(f"  Created Season 2024 (ID {season_2024['id']})")

    patch(base, f"/seasons/{season_2024['id']}/", {"is_archived": True}, admin_token)
    print("  Archived Season 2024")

    season_2025 = post(
        base,
        "/seasons/",
        {
            "name": "WFL Premier 2025",
            "year": 2025,
            "registration_open_at": "2025-01-01T00:00:00+00:00",
            "registration_close_at": "2026-12-31T23:59:59+00:00",
        },
        admin_token,
    )
    season_id = season_2025["id"]
    print(f"  Created Season 2025 (ID {season_id}) — status: OPEN\n")

    # ── 3. Clubs ────────────────────────────────────────────────
    print(f"{sep}\n  Creating clubs...")
    club_ids: list[int] = []
    for club_data in CLUBS:
        club = post(base, "/clubs/", club_data, admin_token)
        club_ids.append(club["id"])
        print(f"  Created {club_data['name']} (ID {club['id']})")
    print()

    # ── 4. League admin ─────────────────────────────────────────
    print(f"{sep}\n  Creating league admin...")
    la_user = post(
        base,
        "/users/",
        {
            **{k: v for k, v in LEAGUE_ADMIN.items() if k != "club_index"},
            "temporary_password": TEMP_PASSWORD,
            "member_type": "user",
        },
        admin_token,
    )
    print(f"  Created {LEAGUE_ADMIN['full_name']} (ID {la_user['id']})\n")

    # ── 5. Club admins ──────────────────────────────────────────
    print(f"{sep}\n  Creating club admins...")
    club_admin_records: list[
        dict
    ] = []  # {user_id, player_id, email, club_id, club_index}
    for ca in CLUB_ADMINS:
        club_id = club_ids[ca["club_index"]]  # type: ignore[call-overload]
        user = post(
            base,
            "/users/",
            {
                "email": ca["email"],
                "role": "club_admin",
                "club_id": club_id,
                "temporary_password": TEMP_PASSWORD,
                "full_name": ca["full_name"],
                "date_of_birth": ca["date_of_birth"],
                "nic_number": ca["nic_number"],
            },
            admin_token,
        )
        club_admin_records.append(
            {
                "user_id": user["id"],
                "player_id": user["player_id"],
                "email": ca["email"],
                "club_id": club_id,
                "club_index": ca["club_index"],
                "full_name": ca["full_name"],
            }
        )
        cname = CLUBS[ca["club_index"]]["name"]  # type: ignore[call-overload]
        print(f"  Created {ca['full_name']} → {cname} (user #{user['id']})")
    print()

    # ── 6. Players ──────────────────────────────────────────────
    print(f"{sep}\n  Creating players...")
    # player_records[club_index] = list of {user_id, player_id, email, full_name}
    player_records: list[list[dict]] = [[], [], []]
    for club_idx, players in enumerate(PLAYERS_BY_CLUB):
        for p in players:
            user = post(
                base,
                "/users/",
                {
                    "email": p["email"],
                    "role": "player",
                    "temporary_password": TEMP_PASSWORD,
                    "full_name": p["full_name"],
                    "date_of_birth": p["date_of_birth"],
                    "nic_number": p["nic_number"],
                },
                admin_token,
            )
            player_records[club_idx].append(
                {
                    "user_id": user["id"],
                    "player_id": user["player_id"],
                    "email": p["email"],
                    "full_name": p["full_name"],
                }
            )
            uid, pid = user["id"], user["player_id"]
            print(f"  Created {p['full_name']} (user #{uid}, player #{pid})")

    print("\n  Creating free players...")
    free_player_records: list[dict] = []
    for fp in FREE_PLAYERS:
        user = post(
            base,
            "/users/",
            {
                "email": fp["email"],
                "role": "player",
                "temporary_password": TEMP_PASSWORD,
                "full_name": fp["full_name"],
                "date_of_birth": fp["date_of_birth"],
                "nic_number": fp["nic_number"],
            },
            admin_token,
        )
        free_player_records.append(
            {
                "user_id": user["id"],
                "player_id": user["player_id"],
                "email": fp["email"],
                "full_name": fp["full_name"],
            }
        )
        print(f"  Created {fp['full_name']} — free player (user #{user['id']})")
    print()

    # ── 7. Set permanent passwords ──────────────────────────────
    print(f"{sep}\n  Setting permanent passwords for all demo users...")
    all_created_emails: list[str] = (
        [str(LEAGUE_ADMIN["email"])]
        + [str(ca["email"]) for ca in CLUB_ADMINS]
        + [str(p["email"]) for club in PLAYERS_BY_CLUB for p in club]
        + [str(fp["email"]) for fp in FREE_PLAYERS]
    )
    for email in all_created_emails:
        first_login_set_password(base, email, TEMP_PASSWORD, DEMO_PASSWORD)
        print(f"  Password set: {email}")
    print()

    # ── 8. Club membership invites ──────────────────────────────
    print(f"{sep}\n  Sending club membership invites...")
    for ca_rec in club_admin_records:
        ca_token = login(base, ca_rec["email"], DEMO_PASSWORD)
        club_idx = ca_rec["club_index"]
        club_name = CLUBS[club_idx]["name"]
        for pr in player_records[club_idx]:
            invite = post(
                base,
                "/club-memberships/requests/",
                {
                    "player_id": pr["player_id"],
                },
                ca_token,
            )
            iid = invite["id"]
            caname, prname = ca_rec["full_name"], pr["full_name"]
            print(f"  {caname} invited {prname} → {club_name} (#{iid})")

    print("\n  Players accepting invites...")
    for club_idx, players in enumerate(player_records):
        for pr in players:
            p_token = login(base, pr["email"], DEMO_PASSWORD)
            # Fetch their pending invites
            invites = get(base, "/club-memberships/requests/", p_token)
            pending = [i for i in invites if i["status"] == "pending"]
            for inv in pending:
                post(
                    base,
                    f"/club-memberships/requests/{inv['id']}/decide/",
                    {
                        "decision": "accept",
                    },
                    p_token,
                )
            print(f"  {pr['full_name']} joined {CLUBS[club_idx]['name']}")
    print()

    # ── 9. Squad registrations for Season 2025 ──────────────────
    print(f"{sep}\n  Sending Season 2025 squad registration requests...")
    for ca_rec in club_admin_records:
        ca_token = login(base, ca_rec["email"], DEMO_PASSWORD)
        club_idx = ca_rec["club_index"]
        for pr in player_records[club_idx]:
            reg = post(
                base,
                "/registration-requests/",
                {
                    "player_id": pr["player_id"],
                    "club_id": ca_rec["club_id"],
                    "season_id": season_id,
                },
                ca_token,
            )
            print(f"  Sent reg request to {pr['full_name']} (req #{reg['id']})")

    print("\n  Players acknowledging registrations...")
    for players in player_records:
        for pr in players:
            p_token = login(base, pr["email"], DEMO_PASSWORD)
            regs = get(base, "/registration-requests/", p_token)
            pending = [r for r in regs if r["status"] == "pending_player_confirmation"]
            for reg in pending:
                post(
                    base,
                    f"/registration-requests/{reg['id']}/decide/",
                    {
                        "decision": "accept",
                    },
                    p_token,
                )
            print(f"  {pr['full_name']} acknowledged registration")
    print()

    # ── 10. Summary ─────────────────────────────────────────────
    print(f"{'=' * 56}")
    print("  SEED COMPLETE")
    print(f"{'=' * 56}\n")
    print("  All demo accounts use password:  Demo@2026!\n")

    rows: list[tuple[str, str, str]] = [
        ("Role", "Name", "Email"),
        ("────", "────", "─────"),
        ("league_admin", str(LEAGUE_ADMIN["full_name"]), str(LEAGUE_ADMIN["email"])),
    ]
    for i, ca in enumerate(CLUB_ADMINS):
        ca_label = str(ca["full_name"]) + f"  [{CLUBS[i]['name']}]"
        rows.append(("club_admin", ca_label, str(ca["email"])))
    for club_idx, players in enumerate(PLAYERS_BY_CLUB):
        for p in players:
            rows.append(
                (
                    "player",
                    str(p["full_name"]) + f"  [{CLUBS[club_idx]['name']}]",
                    str(p["email"]),
                )
            )
    for fp in FREE_PLAYERS:
        rows.append(("player", str(fp["full_name"]) + "  [free]", str(fp["email"])))

    col_w = [max(len(r[i]) for r in rows) for i in range(3)]
    for row in rows:
        print("  " + "  ".join(row[i].ljust(col_w[i]) for i in range(3)))

    print("\n  Seasons  : WFL Premier 2024 (archived)  |  WFL Premier 2025 (open)")
    print(f"  Clubs    : {', '.join(c['name'] for c in CLUBS)}")
    print("  Players  : 12 registered in Season 2025  |  2 free players\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed WFL demo data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Run from")[0].strip(),
    )
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--email", default="", help="Super admin email")
    parser.add_argument("--password", default="", help="Super admin password")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without making requests",
    )
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
        return

    if not args.email or not args.password:
        print("Error: --email and --password are required unless --dry-run is set")
        sys.exit(1)

    try:
        seed(args.api.rstrip("/"), args.email, args.password)
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
