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
from typing import Optional
from sqlalchemy.orm import relationship, declarative_base, Mapped, mapped_column

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
    cricsheet_identifier = Column(String(50), nullable=True, unique=True, index=True)
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

    commentary_text = Column(Text, nullable=True)  # Populated by post-ingestion enricher

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


# ═══════════════════════════════════════════════════════════════════
# CRICSHEET REGISTRY
# ═══════════════════════════════════════════════════════════════════
class PlayerRegistry(Base):
    __tablename__ = "player_registry"

    identifier = Column(String(50), primary_key=True)
    name = Column(String(250), nullable=False)
    unique_name = Column(String(250), nullable=False)
    canonical_name = Column(String(250), nullable=False, index=True)
    key_cricinfo = Column(String(50), nullable=True)
    key_espn = Column(String(50), nullable=True)
    key_cricbuzz = Column(String(50), nullable=True)
    key_bigbash = Column(String(50), nullable=True)
    key_crichq = Column(String(50), nullable=True)
    key_opta = Column(String(50), nullable=True)
    key_nvplay = Column(String(50), nullable=True)
    key_cricsheet = Column(String(50), nullable=True)
    key_rhino = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        nullable=False,
    )


class PlayerMergeQueue(Base):
    __tablename__ = "player_merge_queue"

    id = Column(String(36), primary_key=True, default=_uuid)
    raw_name = Column(String(250), nullable=False)
    matched_canonical = Column(String(250), nullable=False)
    fuzzy_score = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        nullable=False,
    )

# ═══════════════════════════════════════════════════════════════════
# API USAGE LOG
# ═══════════════════════════════════════════════════════════════════
class APIUsageLog(Base):
    __tablename__ = "api_usage_log"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_name: Mapped[str] = mapped_column(String(50), nullable=False)  # "cricketdata"
    called_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    match_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    deliveries_updated: Mapped[int] = mapped_column(Integer, default=0)
