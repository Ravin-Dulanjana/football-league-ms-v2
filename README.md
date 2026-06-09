# Football League Management System v2

[![CI/CD Pipeline](https://github.com/Ravin-Dulanjana/football-league-ms-v2/actions/workflows/deploy.yml/badge.svg)](https://github.com/Ravin-Dulanjana/football-league-ms-v2/actions/workflows/deploy.yml)

A REST API for managing football clubs, seasons, player registrations, and player releases. Built with FastAPI, SQLAlchemy 2.0, and PostgreSQL. Deployed to AWS EC2 with automated CI/CD via GitHub Actions.

## Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Database | PostgreSQL 15 |
| Migrations | Alembic |
| Server | Gunicorn + Uvicorn workers |
| Reverse proxy | nginx |
| Infrastructure | AWS CDK (EC2 + VPC) |
| CI/CD | GitHub Actions |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET/POST | `/clubs/` | List all active clubs / create a club |
| GET/PATCH | `/clubs/{id}/` | Get or update a club |
| GET/POST | `/seasons/` | List seasons / create a season |
| PATCH | `/seasons/{id}/` | Update season (status transitions) |
| GET/POST | `/players/` | List players / register a player |
| GET/PATCH | `/players/{id}/` | Get or update a player |
| POST | `/registration-requests/` | Request a player registration |
| POST | `/registration-requests/{id}/decide/` | Accept or reject a request |
| POST | `/releases/` | Initiate a player release |
| POST | `/releases/{id}/decide/` | Confirm or reject a release |

Interactive docs: `GET /docs`

## Running Locally

```bash
# 1. Clone and enter the repo
git clone https://github.com/Ravin-Dulanjana/football-league-ms-v2.git
cd football-league-ms-v2

# 2. Create a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install dev dependencies
pip install -e ".[dev]"

# 4. Copy the example env file and fill in your DATABASE_URL
cp .env.example .env

# 5. Run migrations
alembic upgrade head

# 6. Start the server
uvicorn main:app --reload
```

## Running Tests

Tests use an in-memory SQLite database — no PostgreSQL server required.

```bash
pytest tests/ -v
```

## CI/CD Pipeline

Every push to `main` triggers the pipeline in `.github/workflows/deploy.yml`:

1. **Test job** — checks out code, installs dependencies, runs `ruff check` and `pytest`
2. **Deploy job** — only runs if the test job passes; SSHs into the EC2 and runs `git pull`, `pip install`, `alembic upgrade head`, `systemctl restart gunicorn`

Required GitHub Secrets: `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`

## Project Structure

```
app/
  models/      SQLAlchemy ORM models
  schemas/     Pydantic request/response schemas
  services/    Business logic (no FastAPI dependencies)
  routers/     FastAPI route handlers
  config.py    Settings loaded from .env
  db.py        Database engine and session factory
alembic/       Database migration scripts
infra/         AWS CDK stack (EC2, VPC, security groups)
tests/         pytest test suite
main.py        FastAPI application entry point
```
