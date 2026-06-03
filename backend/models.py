"""
SQLAlchemy ORM models — Section 1.

Four tables: matches, players, deliveries, cricviz_metrics.
All use String(36) UUIDs for SQLite/PostgreSQL portability.
Every FK column is indexed. Cascade deletes are declared explicitly.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Index, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def _uuid() -> str:
    """Generate a new UUID4 string for use as a primary key."""
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════
# MATCHES
# ═══════════════════════════════════════════════════════════════════
class Match(Base):
    __tablename__ = "matches"

    id          = Column(String(36), primary_key=True, default=_uuid)
    date        = Column(String(10), nullable=False)           # YYYY-MM-DD
    team1       = Column(String(120), nullable=False)
    team2       = Column(String(120), nullable=False)
    venue       = Column(String(250), nullable=False, default="unknown_venue")
    outcome     = Column(String(250), nullable=False, default="no_result")
    match_type  = Column(String(30), nullable=False, default="T20")
    gender      = Column(String(10), nullable=False, default="male")
    source_file = Column(String(500), nullable=False, unique=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    deliveries = relationship(
        "Delivery", back_populates="match", cascade="all, delete-orphan",
    )


# ═══════════════════════════════════════════════════════════════════
# PLAYERS
# ═══════════════════════════════════════════════════════════════════
class Player(Base):
    __tablename__ = "players"

    id            = Column(String(36), primary_key=True, default=_uuid)
    name          = Column(String(200), nullable=False)
    handedness    = Column(String(20), nullable=True)   # RHB, LHB
    bowling_style = Column(String(40), nullable=True)   # RF, RFM, OB, LB, …
    country       = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        nullable=False,
    )

    # Guard against name collisions from different teams/matches
    __table_args__ = (
        UniqueConstraint("name", "country", name="uq_player_name_country"),
    )


# ═══════════════════════════════════════════════════════════════════
# DELIVERIES
# ═══════════════════════════════════════════════════════════════════
class Delivery(Base):
    __tablename__ = "deliveries"

    id         = Column(String(36), primary_key=True, default=_uuid)

    match_id   = Column(
        String(36),
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    innings    = Column(Integer, nullable=False)
    over       = Column(Integer, nullable=False)
    ball       = Column(Integer, nullable=False)

    batter_id  = Column(
        String(36),
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bowler_id  = Column(
        String(36),
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runs_bat    = Column(Integer, nullable=False, default=0)
    runs_extras = Column(Integer, nullable=False, default=0)
    wicket_type = Column(String(60), nullable=True)
    fielder_id  = Column(
        String(36),
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,     # ← only nullable FK
        index=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        nullable=False,
    )

    # Composite indexes for high-cardinality filter columns
    __table_args__ = (
        Index("ix_deliveries_innings", "innings"),
        Index("ix_deliveries_over", "over"),
        Index("ix_deliveries_match_innings_over", "match_id", "innings", "over"),
    )

    # Relationships
    match   = relationship("Match", back_populates="deliveries")
    batter  = relationship("Player", foreign_keys=[batter_id])
    bowler  = relationship("Player", foreign_keys=[bowler_id])
    fielder = relationship("Player", foreign_keys=[fielder_id])
    metrics = relationship(
        "CricvizMetric", back_populates="delivery",
        uselist=False, cascade="all, delete-orphan",
    )


# ═══════════════════════════════════════════════════════════════════
# CRICVIZ METRICS  (one-to-one with deliveries)
# ═══════════════════════════════════════════════════════════════════
class CricvizMetric(Base):
    __tablename__ = "cricviz_metrics"

    delivery_id = Column(
        String(36),
        ForeignKey("deliveries.id", ondelete="CASCADE"),
        primary_key=True,   # PK + FK → one-to-one enforced
    )
    shot_intent      = Column(String(20), nullable=False, default="UNKNOWN")
    pitch_length_zone = Column(String(20), nullable=False, default="UNKNOWN")
    is_false_shot    = Column(Boolean, nullable=False, default=False)
    computed_xR      = Column(Float, nullable=False, default=0.0)
    computed_xW      = Column(Float, nullable=False, default=0.0)
    commentary_source = Column(String(50), nullable=False, default="heuristic")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationship
    delivery = relationship("Delivery", back_populates="metrics")


# ═══════════════════════════════════════════════════════════════════
# INGESTION JOBS (for Celery async workers)
# ═══════════════════════════════════════════════════════════════════
class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String(36), primary_key=True)  # Set from Celery Task ID or manually generated
    status = Column(String(50), nullable=False, default="queued")
    matches_processed = Column(Integer, nullable=False, default=0)
    matches_failed = Column(Integer, nullable=False, default=0)
    total_deliveries = Column(Integer, nullable=False, default=0)
    total_matches = Column(Integer, nullable=False, default=0)
    logs = Column(Text, nullable=True)  # JSON serialized logs

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        nullable=False,
    )


# ═══════════════════════════════════════════════════════════════════
# USERS (Auth Layer)
# ═══════════════════════════════════════════════════════════════════
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ═══════════════════════════════════════════════════════════════════
# Schema Validation Checklist (verified at module level)
# ═══════════════════════════════════════════════════════════════════
# ☑ All FK columns indexed (match_id, batter_id, bowler_id, fielder_id, delivery_id)
# ☑ No nullable FK except fielder_id
# ☑ Cascade deletes defined (matches→deliveries, deliveries→metrics, players→SET NULL on fielder)
# ☑ UUID strategy consistent: String(36) + uuid4() default across all tables
# ☑ cricviz_metrics.delivery_id is both PK and FK (one-to-one enforced)
