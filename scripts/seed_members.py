"""
Seed 30 member accounts via the API.

All members are created as players with temporary password: Welcome1!
They will be prompted to change it on first login.

Usage (local):
    python scripts/seed_members.py \
        --api http://localhost:8000 \
        --email admin@example.com \
        --password "YourAdminPassword"

Usage (EC2):
    python scripts/seed_members.py \
        --api http://3.1.116.7 \
        --email admin@example.com \
        --password "YourAdminPassword"

Dry run (no requests made):
    python scripts/seed_members.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Member data — 30 players
# ---------------------------------------------------------------------------

TEMP_PASSWORD = "Welcome1!"

MEMBERS = [
    {
        "full_name": "Ashan Perera",
        "date_of_birth": "1998-03-14",
        "nic_number": "982730151V",
        "email": "member01@test.lk",
    },
    {
        "full_name": "Nuwan Silva",
        "date_of_birth": "2000-07-22",
        "nic_number": "200203510V",
        "email": "member02@test.lk",
    },
    {
        "full_name": "Kasun Fernando",
        "date_of_birth": "1997-11-05",
        "nic_number": "973095821V",
        "email": "member03@test.lk",
    },
    {
        "full_name": "Lahiru Jayantha",
        "date_of_birth": "2001-01-30",
        "nic_number": "200103081V",
        "email": "member04@test.lk",
    },
    {
        "full_name": "Ruwan Dissanayake",
        "date_of_birth": "1999-06-18",
        "nic_number": "991700411V",
        "email": "member05@test.lk",
    },
    {
        "full_name": "Saman Bandara",
        "date_of_birth": "1996-09-12",
        "nic_number": "962561231V",
        "email": "member06@test.lk",
    },
    {
        "full_name": "Dilshan Herath",
        "date_of_birth": "2002-04-03",
        "nic_number": "202093781V",
        "email": "member07@test.lk",
    },
    {
        "full_name": "Chathura Rajapaksa",
        "date_of_birth": "1995-12-25",
        "nic_number": "953600421V",
        "email": "member08@test.lk",
    },
    {
        "full_name": "Tharaka Wijesinghe",
        "date_of_birth": "2003-08-11",
        "nic_number": "200322430V",
        "email": "member09@test.lk",
    },
    {
        "full_name": "Banusha Gunasekara",
        "date_of_birth": "1998-05-20",
        "nic_number": "981410151V",
        "email": "member10@test.lk",
    },
    {
        "full_name": "Malindu Rathnayake",
        "date_of_birth": "2000-02-14",
        "nic_number": "200204510V",
        "email": "member11@test.lk",
    },
    {
        "full_name": "Roshan Kumara",
        "date_of_birth": "1997-09-08",
        "nic_number": "972520821V",
        "email": "member12@test.lk",
    },
    {
        "full_name": "Gayan Madushanka",
        "date_of_birth": "2001-11-27",
        "nic_number": "200133281V",
        "email": "member13@test.lk",
    },
    {
        "full_name": "Priyantha Senanayake",
        "date_of_birth": "1996-04-16",
        "nic_number": "961070031V",
        "email": "member14@test.lk",
    },
    {
        "full_name": "Chamara Jayawardena",
        "date_of_birth": "1999-07-03",
        "nic_number": "991850411V",
        "email": "member15@test.lk",
    },
    {
        "full_name": "Supun Wickramasinghe",
        "date_of_birth": "2002-01-19",
        "nic_number": "200201921V",
        "email": "member16@test.lk",
    },
    {
        "full_name": "Udara Pathirana",
        "date_of_birth": "1995-10-30",
        "nic_number": "953040021V",
        "email": "member17@test.lk",
    },
    {
        "full_name": "Akila Dananjaya",
        "date_of_birth": "2003-06-22",
        "nic_number": "200317430V",
        "email": "member18@test.lk",
    },
    {
        "full_name": "Chanaka Liyanage",
        "date_of_birth": "1998-12-11",
        "nic_number": "983461521V",
        "email": "member19@test.lk",
    },
    {
        "full_name": "Jeewa Mendis",
        "date_of_birth": "2000-03-05",
        "nic_number": "200006551V",
        "email": "member20@test.lk",
    },
    {
        "full_name": "Kavindu Hasantha",
        "date_of_birth": "1997-08-17",
        "nic_number": "972300821V",
        "email": "member21@test.lk",
    },
    {
        "full_name": "Nadeeka Prasad",
        "date_of_birth": "2001-05-09",
        "nic_number": "200113081V",
        "email": "member22@test.lk",
    },
    {
        "full_name": "Tilan Samaraweera",
        "date_of_birth": "1996-11-24",
        "nic_number": "963290031V",
        "email": "member23@test.lk",
    },
    {
        "full_name": "Asanka Gunawardana",
        "date_of_birth": "1999-02-28",
        "nic_number": "990591411V",
        "email": "member24@test.lk",
    },
    {
        "full_name": "Prabath Niroshan",
        "date_of_birth": "2002-09-15",
        "nic_number": "202591521V",
        "email": "member25@test.lk",
    },
    {
        "full_name": "Vimukthi Abeyratne",
        "date_of_birth": "1995-06-07",
        "nic_number": "951590021V",
        "email": "member26@test.lk",
    },
    {
        "full_name": "Ranidu Perera",
        "date_of_birth": "2003-04-01",
        "nic_number": "200309230V",
        "email": "member27@test.lk",
    },
    {
        "full_name": "Sachith Pathirage",
        "date_of_birth": "1998-10-18",
        "nic_number": "982921521V",
        "email": "member28@test.lk",
    },
    {
        "full_name": "Dushan Siriwardena",
        "date_of_birth": "2000-08-25",
        "nic_number": "200223851V",
        "email": "member29@test.lk",
    },
    {
        "full_name": "Minura Jayasundara",
        "date_of_birth": "1997-01-12",
        "nic_number": "970120821V",
        "email": "member30@test.lk",
    },
]

# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no extra deps)
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
# Main
# ---------------------------------------------------------------------------


def seed(api_base: str, admin_email: str, admin_password: str, dry_run: bool) -> None:
    if dry_run:
        print("[DRY RUN] Would create the following 30 members:")
        print(f"  Temporary password for all: {TEMP_PASSWORD}")
        print()
        for i, m in enumerate(MEMBERS, 1):
            print(f"  {i:02d}. {m['full_name']:<28} {m['email']}")
        return

    # Login
    print(f"\nLogging in as {admin_email}...")
    tokens = _request(
        "POST",
        f"{api_base}/auth/login",
        {"email": admin_email, "password": admin_password},
    )
    token = tokens["id_token"]
    print("  Login OK\n")

    created = 0
    failed = 0

    for i, m in enumerate(MEMBERS, 1):
        print(
            f"[{i:02d}/30] Creating {m['full_name']} ({m['email']})...",
            end=" ",
            flush=True,
        )
        try:
            user = post(
                api_base,
                "/users/",
                {
                    "email": m["email"],
                    "temporary_password": TEMP_PASSWORD,
                    "role": "player",
                    "member_type": "player",
                    "full_name": m["full_name"],
                    "date_of_birth": m["date_of_birth"],
                    "nic_number": m["nic_number"],
                },
                token,
            )
            print(f"OK (user #{user['id']}, player #{user['player_id']})")
            created += 1
        except RuntimeError as exc:
            print(f"FAILED\n  {exc}")
            failed += 1

    print(f"\nDone — {created} created, {failed} failed.")
    if created:
        print(f"Temporary password for all accounts: {TEMP_PASSWORD}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed 30 member accounts")
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--email", default="", help="Admin email to log in with")
    parser.add_argument("--password", default="", help="Admin password")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without making requests",
    )
    args = parser.parse_args()

    if not args.dry_run and (not args.email or not args.password):
        print("Error: --email and --password are required unless --dry-run is set.")
        sys.exit(1)

    seed(args.api, args.email, args.password, args.dry_run)


if __name__ == "__main__":
    main()
