"""
Alembic migration environment — wired to the app's config and models.

Uses DATABASE_URL from config.py so there is a single source of truth
for the connection string.  Imports Base.metadata from models.py to
enable autogenerate support.
"""
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Ensure the backend package is importable ─────────────────────
# When Alembic runs from the backend/ directory, sys.path should
# already include '.', but we make it explicit just in case.
_backend_dir = str(Path(__file__).resolve().parents[1])
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# ── Import app config and models ─────────────────────────────────
from config import DATABASE_URL          # noqa: E402
from models import Base                  # noqa: E402

# Alembic Config object (reads alembic.ini)
config = context.config

# Override the sqlalchemy.url from alembic.ini with the app's DATABASE_URL
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Set up Python loggers from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script generation)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Required for SQLite ALTER TABLE support
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
