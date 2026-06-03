"""
Database engine and session factory.

Connection pool is configured for PostgreSQL; SQLite falls back to defaults.
Every session is scoped to a request or a unit-of-work via `get_db()`.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from config import (
    DATABASE_URL, POOL_TIMEOUT, POOL_RECYCLE,
    POOL_SIZE, POOL_MAX_OVERFLOW,
)

# ── Engine ───────────────────────────────────────────────────────
_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    # Enable WAL mode and foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()
else:
    engine = create_engine(
        DATABASE_URL,
        pool_timeout=POOL_TIMEOUT,
        pool_recycle=POOL_RECYCLE,
        pool_size=POOL_SIZE,
        max_overflow=POOL_MAX_OVERFLOW,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Dependency ───────────────────────────────────────────────────
def get_db():
    """FastAPI dependency — yields a session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context-manager variant for non-request code (ingestion, scripts)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
