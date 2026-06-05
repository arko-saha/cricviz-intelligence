"""
Commentary Client — thin façade for ingestion-time commentary lookup.

Delegates to :class:`~ingestion.commentary_provider.CricAPIProvider`
so both the ingestion pipeline and the post-ingestion enricher share
the same HTTP / parsing logic.

Called during ingestion (see ``ingestion_service.ingest_match_dict``)
with team names and date extracted from the Cricsheet JSON.
"""
from __future__ import annotations

import logging
from typing import Dict

from ingestion.commentary_provider import CricAPIProvider

logger = logging.getLogger("cricviz.commentary")

# Module-level singleton — avoids re-reading config per call.
_provider = CricAPIProvider()


def fetch_match_commentary(
    team1: str,
    team2: str,
    match_date: str,
) -> Dict[str, str]:
    """
    Fetch full match commentary from CricAPI by team names and date.

    Uses the public ``CommentaryProvider`` protocol method which
    resolves the CricAPI match ID via team + date search, then
    fetches the scorecard commentary.

    Args:
        team1: Name of the first team.
        team2: Name of the second team.
        match_date: Match date as ``YYYY-MM-DD``.

    Returns:
        Mapping of ``"innings_over_ball"`` → commentary text.
        Empty dict when no data is available or on any error.
    """
    import config

    if not config.CRICAPI_KEY:
        return {}

    try:
        return _provider.fetch_commentary(
            team1=team1,
            team2=team2,
            match_date=match_date,
        )
    except Exception as exc:
        logger.warning(
            "CricAPI commentary fetch failed for %s vs %s (%s): %s",
            team1, team2, match_date, exc,
        )
        return {}
