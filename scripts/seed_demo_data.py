"""
Demo data seeding script.

Creates a realistic set of demo data via the API:
  - 1 current season (registration open)
  - 4 clubs
  - 4 players per club (16 total)
  - Registration requests for every player → their club
  - All registrations approved

Usage:
    python scripts/seed_demo_data.py --api http://<EC2_IP> \
        --email admin@football.com --password "YourPassword"

    # Dry run (prints what would be created, makes no requests):
    python scripts/seed_demo_data.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

# ---------------------------------------------------------------------------
# Demo data definitions
# ---------------------------------------------------------------------------

CLUBS = [
    {
        "name": "Colombo FC",
        "short_name": "CFO",
        "code": "CFO",
        "email": "colombo@league.lk",
    },
    {
        "name": "Kandy United",
        "short_name": "KND",
        "code": "KND",
        "email": "kandy@league.lk",
    },
    {
        "name": "Galle City",
        "short_name": "GAL",
        "code": "GAL",
        "email": "galle@league.lk",
    },
    {
        "name": "Jaffna Rangers",
        "short_name": "JRG",
        "code": "JRG",
        "email": "jaffna@league.lk",
    },
]

# 4 players per club — indexed [club_index][player]
PLAYERS_BY_CLUB = [
    [
        {
            "full_name": "Ashan Perera",
            "date_of_birth": "1998-03-14",
            "nic_number": "982730150V",
        },
        {
            "full_name": "Nuwan Silva",
            "date_of_birth": "2000-07-22",
            "nic_number": "200720350V",
        },
        {
            "full_name": "Kasun Fernando",
            "date_of_birth": "1997-11-05",
            "nic_number": "973095820V",
        },
        {
            "full_name": "Lahiru Jayantha",
            "date_of_birth": "2001-01-30",
            "nic_number": "200103080V",
        },
    ],
    [
        {
            "full_name": "Ruwan Dissanayake",
            "date_of_birth": "1999-06-18",
            "nic_number": "991700410V",
        },
        {
            "full_name": "Saman Bandara",
            "date_of_birth": "1996-09-12",
            "nic_number": "962561230V",
        },
        {
            "full_name": "Dilshan Herath",
            "date_of_birth": "2002-04-03",
            "nic_number": "202093780V",
        },
        {
            "full_name": "Chamara Kumara",
            "date_of_birth": "1995-12-25",
            "nic_number": "953600510V",
        },
    ],
    [
        {
            "full_name": "Pradeep Rajapaksa",
            "date_of_birth": "1998-08-07",
            "nic_number": "982201850V",
        },
        {
            "full_name": "Tharaka Mendis",
            "date_of_birth": "2003-02-14",
            "nic_number": "203450920V",
        },
        {
            "full_name": "Buddhika Gunawardena",
            "date_of_birth": "1997-05-29",
            "nic_number": "971500480V",
        },
        {
            "full_name": "Hasitha Liyanage",
            "date_of_birth": "2001-10-11",
            "nic_number": "201851220V",
        },
    ],
    [
        {
            "full_name": "Nirosh Arumugam",
            "date_of_birth": "1999-03-22",
            "nic_number": "990811450V",
        },
        {
            "full_name": "Jegan Selvaraj",
            "date_of_birth": "1996-07-04",
            "nic_number": "961861720V",
        },
        {
            "full_name": "Kumaran Navaratnam",
            "date_of_birth": "2000-11-19",
            "nic_number": "200324580V",
        },
        {
            "full_name": "Siva Rajaratnam",
            "date_of_birth": "2002-06-30",
            "nic_number": "202821360V",
        },
    ],
]


# ---------------------------------------------------------------------------
# Minimal HTTP client (no external deps)
# ---------------------------------------------------------------------------


def _request(
    method: str, url: str, body: dict | None = None, token: str | None = None
) -> dict:
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return dict(json.loads(resp.read()))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} {method} {url}\n{body_text}") from e


def post(base: str, path: str, body: dict, token: str) -> dict:
    return _request("POST", f"{base}{path}", body, token)


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------


def seed(api_base: str, email: str, password: str, dry_run: bool) -> None:
    if dry_run:
        print("[DRY RUN] Would create:")
        print("  1 season")
        print(f"  {len(CLUBS)} clubs")
        total_players = sum(len(p) for p in PLAYERS_BY_CLUB)
        print(f"  {total_players} players")
        print(f"  {total_players} registration requests (all approved)")
        return

    # -- Login ---------------------------------------------------------------
    print(f"\nLogging in as {email}...")
    tokens = _request(
        "POST", f"{api_base}/auth/login", {"email": email, "password": password}
    )
    token = tokens["id_token"]
    print("  Login OK")

    # -- Season --------------------------------------------------------------
    now = datetime.now(tz=UTC)
    season_payload = {
        "name": f"Premier League {now.year}",
        "year": now.year,
        "registration_open_at": (now - timedelta(days=7)).isoformat(),
        "registration_close_at": (now + timedelta(days=60)).isoformat(),
    }
    print(f"\nCreating season: {season_payload['name']}...")
    season = post(api_base, "/seasons/", season_payload, token)
    season_id = season["id"]
    print(f"  Created season #{season_id}")

    # -- Clubs + Players + Registrations ------------------------------------
    for club_idx, club_data in enumerate(CLUBS):
        print(f"\nCreating club: {club_data['name']}...")
        club = post(api_base, "/clubs/", club_data, token)
        club_id = club["id"]
        print(f"  Created club #{club_id}")

        for player_data in PLAYERS_BY_CLUB[club_idx]:
            print(f"  Creating player: {player_data['full_name']}...")
            player = post(api_base, "/players/", player_data, token)
            player_id = player["id"]
            print(f"    Created player #{player_id}")

            print("    Submitting registration request...")
            reg = post(
                api_base,
                "/registration-requests/",
                {
                    "player_id": player_id,
                    "club_id": club_id,
                    "season_id": season_id,
                },
                token,
            )
            reg_id = reg["id"]
            print(f"    Created registration #{reg_id}")

            print("    Approving registration...")
            post(
                api_base,
                f"/registration-requests/{reg_id}/decide/",
                {"decision": "accept"},
                token,
            )
            print("    Approved")

    print("\nDone! Demo data seeded successfully.")
    print("\nSummary:")
    print(f"  Season:  {season_payload['name']} (ID {season_id})")
    print(f"  Clubs:   {len(CLUBS)}")
    print(f"  Players: {sum(len(p) for p in PLAYERS_BY_CLUB)}")
    print("  Registrations: all approved")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed demo data into Football League MS"
    )
    parser.add_argument(
        "--api",
        default="http://localhost",
        help="API base URL (e.g. http://54.179.73.13)",
    )
    parser.add_argument("--email", default="", help="Super admin email")
    parser.add_argument("--password", default="", help="Super admin password")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without making requests",
    )
    args = parser.parse_args()

    if not args.dry_run and (not args.email or not args.password):
        print("Error: --email and --password are required unless --dry-run is set")
        sys.exit(1)

    seed(args.api.rstrip("/"), args.email, args.password, args.dry_run)


if __name__ == "__main__":
    main()
