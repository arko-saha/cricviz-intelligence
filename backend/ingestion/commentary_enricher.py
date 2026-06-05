"""
Commentary Enricher — post-ingestion async enrichment pipeline.

Given matches already stored in the database, this module:
1. Fetches ball-by-ball commentary from a ``CommentaryProvider``.
2. Persists ``commentary_text`` on each ``Delivery`` row.
3. Re-runs the enrichment engine with commentary so the NLP-token
   path fires (replacing coarser heuristic-based xR / xW values).

Designed to be called from:
- Celery Beat schedule (nightly for recent matches).
- Manual API endpoint.
- One-off backfill script.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

import config
from database import get_db_context
from ingestion.commentary_provider import CricAPIProvider, CommentaryProvider
from models import CricvizMetric, Delivery, Match, Player, APIUsageLog
from service.enrichment import enrich_delivery
from fastapi import HTTPException

logger = logging.getLogger("cricviz.commentary_enricher")


# ═══════════════════════════════════════════════════════════════════
# RESULT DATACLASS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EnrichmentResult:
    """Outcome of enriching a single match with commentary."""

    match_id: str
    team1: str = ""
    team2: str = ""
    deliveries_updated: int = 0
    deliveries_skipped: int = 0
    api_found: bool = False
    duration_ms: int = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and self.api_found


# ═══════════════════════════════════════════════════════════════════
# API TRACKING
# ═══════════════════════════════════════════════════════════════════
def get_daily_usage(db: Session, api_name: str = "cricketdata") -> int:
    """Return count of API calls made today (UTC) for this api_name."""
    from sqlalchemy import func
    today = datetime.utcnow().date()
    return db.query(APIUsageLog).filter(
        APIUsageLog.api_name == api_name,
        func.date(APIUsageLog.called_at) == today
    ).count()

# ═══════════════════════════════════════════════════════════════════
# SINGLE-MATCH ENRICHMENT
# ═══════════════════════════════════════════════════════════════════

def enrich_match(
    match_id: str,
    provider: Optional[CommentaryProvider] = None,
    db: Optional[Session] = None,
) -> EnrichmentResult:
    """
    Enrich a single match with commentary from an external provider.

    For each delivery in the match where ``commentary_text IS NULL``:
      - Looks up commentary by ``innings_over_ball`` key.
      - Sets ``delivery.commentary_text``.
      - Re-runs ``enrich_delivery()`` and updates the linked
        ``CricvizMetric`` row.

    Args:
        match_id: Internal DB match ID.
        provider: Commentary source.  Defaults to ``CricAPIProvider``.
        db: Optional SQLAlchemy session.  A fresh session is created
            if ``None``.

    Returns:
        ``EnrichmentResult`` with counts and status.
    """
    if provider is None:
        provider = CricAPIProvider()

    import os
    CRICKETDATA_KEY = os.getenv("CRICKETDATA_KEY") or os.getenv("CRICAPI_KEY")
    if not CRICKETDATA_KEY:
        logger.warning("CRICKETDATA_KEY not set — commentary enrichment skipped")
        return EnrichmentResult(match_id=match_id, api_found=False, error="API Key not configured")

    start = time.time()
    result = EnrichmentResult(match_id=match_id)

    owns_session = db is None
    if owns_session:
        ctx = get_db_context()
        db = ctx.__enter__()

    try:
        # Check daily usage limit
        daily_used = get_daily_usage(db)
        if daily_used >= 95:  # leave 5 in reserve
            raise HTTPException(status_code=503, detail=f"Daily API budget nearly exhausted ({daily_used}/100). Try tomorrow.")

        # ── Load match ───────────────────────────────────────────
        match: Optional[Match] = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            result.error = f"Match {match_id} not found"
            return result

        result.team1 = match.team1
        result.team2 = match.team2

        # ── Fetch commentary from provider ───────────────────────
        commentary_map = provider.fetch_commentary(
            team1=match.team1,
            team2=match.team2,
            match_date=match.date,
        )

        if not commentary_map:
            result.api_found = False
            logger.info(
                "No commentary found for %s vs %s (%s) — skipping",
                match.team1, match.team2, match.date,
            )
            return result

        result.api_found = True

        # ── Load deliveries that need commentary ─────────────────
        deliveries: List[Delivery] = (
            db.query(Delivery)
            .filter(
                and_(
                    Delivery.match_id == match_id,
                    Delivery.commentary_text.is_(None),
                )
            )
            .options(
                joinedload(Delivery.bowler),
                joinedload(Delivery.metrics),
            )
            .order_by(Delivery.innings, Delivery.over, Delivery.ball)
            .all()
        )

        if not deliveries:
            logger.debug("All deliveries already have commentary for match %s", match_id)
            return result

        # ── Track over-level state for enrichment context ────────
        current_innings: Optional[int] = None
        current_over: Optional[int] = None
        wickets_in_innings: int = 0
        runs_in_over_so_far: int = 0

        for delivery in deliveries:
            key = f"{delivery.innings}_{delivery.over}_{delivery.ball}"
            commentary_text = commentary_map.get(key, "")

            if not commentary_text:
                result.deliveries_skipped += 1
                continue

            # Reset state trackers on innings/over boundaries
            if delivery.innings != current_innings:
                current_innings = delivery.innings
                wickets_in_innings = 0
                runs_in_over_so_far = 0
                current_over = delivery.over
            elif delivery.over != current_over:
                current_over = delivery.over
                runs_in_over_so_far = 0

            # ── Persist commentary text ──────────────────────────
            delivery.commentary_text = commentary_text

            # ── Re-run enrichment with commentary ────────────────
            bowler_style: str = ""
            if delivery.bowler:
                bowler_style = delivery.bowler.bowling_style or ""

            del_dict = {
                "runs_bat": delivery.runs_bat,
                "runs": {
                    "batter": delivery.runs_bat,
                    "extras": delivery.runs_extras,
                    "total": delivery.runs_bat + delivery.runs_extras,
                },
                "wicket_type": delivery.wicket_type,
            }

            new_metrics = enrich_delivery(
                del_dict,
                commentary=commentary_text,
                bowler_style=bowler_style,
                innings=delivery.innings,
                over_number=delivery.over,
                runs_in_over_so_far=runs_in_over_so_far,
                wickets_in_innings=wickets_in_innings,
            )

            # ── Update or create CricvizMetric ───────────────────
            metric: Optional[CricvizMetric] = delivery.metrics
            if metric:
                metric.shot_intent = new_metrics["shot_intent"]
                metric.pitch_length_zone = new_metrics["pitch_length_zone"]
                metric.is_false_shot = new_metrics["is_false_shot"]
                metric.computed_xR = new_metrics["computed_xR"]
                metric.computed_xW = new_metrics["computed_xW"]
                metric.commentary_source = new_metrics["commentary_source"]
            else:
                new_metric = CricvizMetric(
                    delivery_id=delivery.id,
                    **new_metrics,
                )
                db.add(new_metric)

            # ── Advance over-level accumulators ──────────────────
            runs_in_over_so_far += delivery.runs_bat + delivery.runs_extras
            if delivery.wicket_type:
                wickets_in_innings += 1

            result.deliveries_updated += 1

        if result.api_found:
            api_log = APIUsageLog(
                api_name="cricketdata",
                match_id=match_id,
                deliveries_updated=result.deliveries_updated
            )
            db.add(api_log)

        db.commit()
        logger.info(
            "Enriched match %s (%s vs %s): %d updated, %d skipped",
            match_id, match.team1, match.team2,
            result.deliveries_updated, result.deliveries_skipped,
        )

    except Exception as exc:
        db.rollback()
        result.error = str(exc)
        logger.exception("Failed to enrich match %s: %s", match_id, exc)

    finally:
        result.duration_ms = int((time.time() - start) * 1000)
        if owns_session:
            ctx.__exit__(None, None, None)

    return result


# ═══════════════════════════════════════════════════════════════════
# BATCH ENRICHMENT — RECENT MATCHES
# ═══════════════════════════════════════════════════════════════════

def enrich_recent_matches(
    days: int | None = None,
    daily_limit: int | None = None,
    provider: Optional[CommentaryProvider] = None,
) -> List[EnrichmentResult]:
    """
    Enrich matches ingested within the last *days* days that still
    have deliveries without commentary.

    Args:
        days: Lookback window.  Defaults to ``COMMENTARY_ENRICH_DAYS``.
        daily_limit: Max matches to process per run.  Defaults to
            ``COMMENTARY_DAILY_LIMIT``.
        provider: Commentary source.  Defaults to ``CricAPIProvider``.

    Returns:
        List of ``EnrichmentResult`` — one per match processed.
    """
    if days is None:
        days = config.COMMENTARY_ENRICH_DAYS
    if daily_limit is None:
        daily_limit = config.COMMENTARY_DAILY_LIMIT
    if provider is None:
        provider = CricAPIProvider()

    cutoff = datetime.utcnow() - timedelta(days=days)
    results: List[EnrichmentResult] = []

    with get_db_context() as db:
        # Find matches ingested recently that still have NULL commentary
        match_ids = _find_matches_needing_commentary(db, since=cutoff, limit=daily_limit)

    logger.info(
        "Commentary enrichment: found %d matches from last %d days (limit %d)",
        len(match_ids), days, daily_limit,
    )

    for match_id in match_ids:
        result = enrich_match(match_id, provider=provider)
        results.append(result)

    _log_batch_summary(results)
    return results


# ═══════════════════════════════════════════════════════════════════
# BATCH ENRICHMENT — FULL BACKFILL
# ═══════════════════════════════════════════════════════════════════

def backfill_all(
    daily_limit: int | None = None,
    provider: Optional[CommentaryProvider] = None,
) -> List[EnrichmentResult]:
    """
    Enrich *all* matches in the database that still have deliveries
    without commentary, regardless of ingestion date.

    Intended for one-off manual execution, not scheduled runs.

    Args:
        daily_limit: Max matches per invocation.  Defaults to
            ``COMMENTARY_DAILY_LIMIT``.
        provider: Commentary source.  Defaults to ``CricAPIProvider``.

    Returns:
        List of ``EnrichmentResult`` — one per match processed.
    """
    if daily_limit is None:
        daily_limit = config.COMMENTARY_DAILY_LIMIT
    if provider is None:
        provider = CricAPIProvider()

    results: List[EnrichmentResult] = []

    with get_db_context() as db:
        match_ids = _find_matches_needing_commentary(db, since=None, limit=daily_limit)

    logger.info(
        "Commentary backfill: found %d matches (limit %d)",
        len(match_ids), daily_limit,
    )

    for match_id in match_ids:
        result = enrich_match(match_id, provider=provider)
        results.append(result)

    _log_batch_summary(results)
    return results


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _find_matches_needing_commentary(
    db: Session,
    since: Optional[datetime] = None,
    limit: int = 90,
) -> List[str]:
    """
    Return match IDs that have at least one delivery with
    ``commentary_text IS NULL``, optionally filtered to matches
    created after *since*.
    """
    q = (
        db.query(Match.id)
        .join(Delivery, Delivery.match_id == Match.id)
        .filter(Delivery.commentary_text.is_(None))
    )

    if since is not None:
        q = q.filter(Match.created_at >= since)

    rows = (
        q.group_by(Match.id)
        .order_by(Match.created_at.desc())
        .limit(limit)
        .all()
    )

    return [row[0] for row in rows]


def _log_batch_summary(results: List[EnrichmentResult]) -> None:
    """Log a summary line for a batch enrichment run."""
    total_updated = sum(r.deliveries_updated for r in results)
    total_skipped = sum(r.deliveries_skipped for r in results)
    api_hits = sum(1 for r in results if r.api_found)
    errors = sum(1 for r in results if r.error)

    logger.info(
        "Commentary enrichment complete: %d matches processed, "
        "%d API hits, %d deliveries updated, %d skipped, %d errors",
        len(results), api_hits, total_updated, total_skipped, errors,
    )
