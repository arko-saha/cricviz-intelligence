"""
Commentary Provider Protocol & CricAPI Adapter.

Defines a pluggable ``CommentaryProvider`` protocol so multiple
data sources (CricAPI, etc) can be swapped without
breaking the ingestion/enrichment layers.  Ships with a production-ready CricAPI
implementation that handles rate-limits, timeouts, and fuzzy
match-ID resolution by team + date.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Protocol, runtime_checkable

import requests

import config

logger = logging.getLogger("cricviz.commentary_provider")


# ═══════════════════════════════════════════════════════════════════
# PROTOCOL
# ═══════════════════════════════════════════════════════════════════

@runtime_checkable
class CommentaryProvider(Protocol):
    """
    Abstract interface for fetching ball-by-ball commentary.

    Implementations must return a flat mapping of delivery keys
    to commentary strings.  Key format: ``"<innings>_<over>_<ball>"``
    (1-indexed innings, 0-indexed overs, 1-indexed ball within over).
    """

    def fetch_commentary(
        self,
        team1: str,
        team2: str,
        match_date: str,
    ) -> Dict[str, str]:
        """
        Fetch commentary for a match identified by the two competing
        teams and the match date (``YYYY-MM-DD``).

        Returns:
            Mapping of ``"innings_over_ball"`` → commentary text.
            Empty dict when no data is available or on any error.
        """
        ...  # pragma: no cover


# ═══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ProviderResult:
    """Structured result from a provider call."""

    commentary: Dict[str, str] = field(default_factory=dict)
    api_match_id: Optional[str] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return bool(self.commentary)


# ═══════════════════════════════════════════════════════════════════
# CricAPI PROVIDER
# ═══════════════════════════════════════════════════════════════════

_CRICAPI_BASE = "https://api.cricapi.com/v1"
_REQUEST_TIMEOUT = 5.0  # seconds


class CricAPIProvider:
    """
    Concrete ``CommentaryProvider`` backed by cricapi.com.

    Resolution strategy:
    1. Search ``/matches`` by team name to find the CricAPI match ID.
    2. Fetch ``/match_scorecard`` for ball-by-ball commentary data.

    All HTTP errors are caught and logged — the provider never raises.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key: str = api_key or config.CRICAPI_KEY

    # ── Public API ───────────────────────────────────────────────

    def fetch_commentary(
        self,
        team1: str,
        team2: str,
        match_date: str,
    ) -> Dict[str, str]:
        """
        Fetch ball-by-ball commentary from CricAPI.

        Args:
            team1: Name of the first team.
            team2: Name of the second team.
            match_date: Match date as ``YYYY-MM-DD``.

        Returns:
            ``{"innings_over_ball": "commentary text", …}``
            or empty dict on failure.
        """
        if not self._api_key:
            logger.debug("CricAPI key not configured — skipping commentary fetch")
            return {}

        result = self._resolve_and_fetch(team1, team2, match_date)
        if result.error:
            logger.warning("CricAPI commentary fetch failed: %s", result.error)
        return result.commentary

    # ── Internal ─────────────────────────────────────────────────

    def _resolve_and_fetch(
        self, team1: str, team2: str, match_date: str
    ) -> ProviderResult:
        """Search for the match on CricAPI, then fetch its commentary."""
        match_id = self._find_match_id(team1, team2, match_date)
        if not match_id:
            return ProviderResult(error=f"Match not found: {team1} vs {team2} on {match_date}")

        return self._fetch_scorecard_commentary(match_id)

    def _find_match_id(
        self, team1: str, team2: str, match_date: str
    ) -> Optional[str]:
        """
        Search CricAPI ``/matches`` by team name and filter by date.

        Tries both team names in case CricAPI indexes on one.
        Returns the first matching ``id`` or ``None``.
        """
        for search_team in (team1, team2):
            try:
                resp = requests.get(
                    f"{_CRICAPI_BASE}/matches",
                    params={"apikey": self._api_key, "search": search_team},
                    timeout=_REQUEST_TIMEOUT,
                )
                if resp.status_code == 429:
                    logger.warning("CricAPI rate-limited during match search")
                    return None
                if resp.status_code != 200:
                    continue

                data = resp.json()
                if data.get("status") != "success":
                    continue

                for match in data.get("data", []):
                    if not match.get("date", "").startswith(match_date):
                        continue
                    # Verify both teams are present
                    teams_raw = " ".join(match.get("teams", [])).lower()
                    t1_lower, t2_lower = team1.lower(), team2.lower()
                    if t1_lower in teams_raw and t2_lower in teams_raw:
                        return match.get("id")

            except requests.RequestException as exc:
                logger.warning("CricAPI match search error for '%s': %s", search_team, exc)
                continue

        return None

    def _fetch_scorecard_commentary(self, match_id: str) -> ProviderResult:
        """
        Fetch ball-by-ball data from ``/match_scorecard``.

        CricAPI returns innings → overs → deliveries with a ``comment``
        field per ball.  We normalise into the flat key format.
        """
        try:
            resp = requests.get(
                f"{_CRICAPI_BASE}/match_scorecard",
                params={"apikey": self._api_key, "id": match_id},
                timeout=_REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                return ProviderResult(error="Rate limited", api_match_id=match_id)
            if resp.status_code != 200:
                return ProviderResult(
                    error=f"HTTP {resp.status_code}", api_match_id=match_id,
                )

            payload = resp.json()
            if payload.get("status") != "success":
                return ProviderResult(
                    error=f"API status: {payload.get('status')}",
                    api_match_id=match_id,
                )

            commentary_map: Dict[str, str] = {}
            match_data = payload.get("data", {})

            # CricAPI scorecard response contains a 'data' dict with
            # ball-by-ball info nested under innings.  The exact
            # structure varies by endpoint version — we attempt
            # multiple known layouts.
            commentary_map = self._parse_commentary_response(match_data)

            return ProviderResult(
                commentary=commentary_map, api_match_id=match_id,
            )

        except requests.RequestException as exc:
            return ProviderResult(
                error=f"Request failed: {exc}", api_match_id=match_id,
            )

    def _parse_commentary_response(
        self, match_data: dict,
    ) -> Dict[str, str]:
        """
        Parse commentary from CricAPI response data.

        Handles two common response shapes:
        1. Flat list of ball events in ``match_data["data"]``
        2. Nested innings → overs → deliveries structure

        Returns ``{innings_over_ball: text}`` mapping.
        """
        result: Dict[str, str] = {}

        # Shape 1: flat ball list (match_commentary endpoint style)
        if isinstance(match_data, list):
            for ball in match_data:
                inn = ball.get("innings", 1)
                ov = ball.get("over", 0)
                b = ball.get("ball", 1)
                text = ball.get("text", "") or ball.get("comment", "")
                if text:
                    result[f"{inn}_{ov}_{b}"] = text
            return result

        # Shape 2: nested structure with scorecard data
        # Try to find commentary in various places
        for key in ("commentary", "ballByBall", "innings"):
            section = match_data.get(key)
            if not section:
                continue

            if isinstance(section, list):
                for item in section:
                    if isinstance(item, dict):
                        inn = item.get("innings", item.get("inning", 1))
                        ov = item.get("over", 0)
                        b = item.get("ball", 1)
                        text = (
                            item.get("text", "")
                            or item.get("comment", "")
                            or item.get("commentary", "")
                        )
                        if text:
                            result[f"{inn}_{ov}_{b}"] = text

        return result
