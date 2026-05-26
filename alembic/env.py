"""Alembic environment configuration.

DATABASE_URL is read from the environment (or .env file via pydantic-settings).
Never hardcode credentials here — this file is committed to git.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Import all models so Alembic can see the full schema for --autogenerate.
# The side-effect of importing app.models is that all ORM mappers are registered
# against Base.metadata before we hand it to Alembic.
import app.models  # noqa: F401
from alembic import context

# ---------------------------------------------------------------------------
# Load app config so DATABASE_URL is available from .env if present
# ---------------------------------------------------------------------------
from app.config import settings
from app.models.base import Base

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Override sqlalchemy.url from our settings (reads DATABASE_URL env var / .env).
# This means credentials NEVER live in alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up Python logging as defined in alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Hand Alembic our full schema so --autogenerate diffs correctly.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# run_migrations_offline
# Generates SQL without a live DB connection (useful for review/dry-run).
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# run_migrations_online
# Connects to the DB and applies pending migrations.
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
