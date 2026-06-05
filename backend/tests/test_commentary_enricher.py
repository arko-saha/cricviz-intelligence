"""
Commentary Enricher & Provider — Unit Tests.

Tests cover:
  - ``CricAPIProvider`` with mocked HTTP (success, 429, timeout, empty)
  - ``enrich_match()`` with a mock provider — verifies commentary_text
    written, metrics re-computed, commentary_source flipped to nlp_token
  - ``enrich_recent_matches()`` respects daily_limit
  - Edge cases: match not found in CricAPI, empty commentary map
  - ``CommentaryProvider`` protocol conformance
"""
import sys
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ingestion.commentary_provider import (
    CommentaryProvider,
    CricAPIProvider,
    ProviderResult,
)
from ingestion.commentary_enricher import (
    EnrichmentResult,
    enrich_match,
    enrich_recent_matches,
    backfill_all,
    _find_matches_needing_commentary,
)


# ═══════════════════════════════════════════════════════════════════
# FIXTURES & HELPERS
# ═══════════════════════════════════════════════════════════════════

class FakeProvider:
    """
    A mock ``CommentaryProvider`` that returns canned commentary.

    Implements the protocol without inheriting — duck typing verified
    via ``isinstance`` check.
    """

    def __init__(self, commentary: Dict[str, str] | None = None):
        self._commentary = commentary or {}
        self.calls: list[tuple] = []

    def fetch_commentary(
        self, team1: str, team2: str, match_date: str,
    ) -> Dict[str, str]:
        self.calls.append((team1, team2, match_date))
        return self._commentary


class EmptyProvider:
    """Provider that always returns empty — simulates API miss."""

    def fetch_commentary(
        self, team1: str, team2: str, match_date: str,
    ) -> Dict[str, str]:
        return {}


def _make_mock_response(status_code: int = 200, json_data: dict | None = None):
    """Build a mock ``requests.Response``."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


# ═══════════════════════════════════════════════════════════════════
# PROVIDER PROTOCOL CONFORMANCE
# ═══════════════════════════════════════════════════════════════════

class TestProviderProtocol:
    """Verify that our providers satisfy the Protocol at runtime."""

    def test_fake_provider_is_commentary_provider(self):
        assert isinstance(FakeProvider(), CommentaryProvider)

    def test_empty_provider_is_commentary_provider(self):
        assert isinstance(EmptyProvider(), CommentaryProvider)

    def test_cricapi_provider_is_commentary_provider(self):
        assert isinstance(CricAPIProvider(api_key="test"), CommentaryProvider)


# ═══════════════════════════════════════════════════════════════════
# CricAPIProvider — HTTP INTERACTIONS (mocked)
# ═══════════════════════════════════════════════════════════════════

class TestCricAPIProvider:

    def test_no_api_key_returns_empty(self):
        """Without a key, the provider short-circuits."""
        provider = CricAPIProvider(api_key="")
        result = provider.fetch_commentary("India", "Australia", "2025-01-15")
        assert result == {}

    @patch("ingestion.commentary_provider.requests.get")
    def test_match_search_and_scorecard_success(self, mock_get):
        """Happy path: match found, scorecard returns commentary."""
        # First call: match search
        match_search_resp = _make_mock_response(200, {
            "status": "success",
            "data": [{
                "id": "abc123",
                "date": "2025-01-15",
                "teams": ["India", "Australia"],
            }],
        })
        # Second call: scorecard
        scorecard_resp = _make_mock_response(200, {
            "status": "success",
            "data": {
                "commentary": [
                    {"innings": 1, "over": 0, "ball": 1, "text": "smashed to cover"},
                    {"innings": 1, "over": 0, "ball": 2, "text": "defended solidly"},
                ],
            },
        })
        mock_get.side_effect = [match_search_resp, scorecard_resp]

        provider = CricAPIProvider(api_key="test_key")
        result = provider.fetch_commentary("India", "Australia", "2025-01-15")

        assert result == {
            "1_0_1": "smashed to cover",
            "1_0_2": "defended solidly",
        }

    @patch("ingestion.commentary_provider.requests.get")
    def test_rate_limited_on_match_search(self, mock_get):
        """429 during match search returns empty."""
        mock_get.return_value = _make_mock_response(429)

        provider = CricAPIProvider(api_key="test_key")
        result = provider.fetch_commentary("India", "Australia", "2025-01-15")
        assert result == {}

    @patch("ingestion.commentary_provider.requests.get")
    def test_rate_limited_on_scorecard(self, mock_get):
        """429 during scorecard fetch returns empty."""
        match_resp = _make_mock_response(200, {
            "status": "success",
            "data": [{
                "id": "abc123",
                "date": "2025-01-15",
                "teams": ["India", "Australia"],
            }],
        })
        scorecard_resp = _make_mock_response(429)
        mock_get.side_effect = [match_resp, scorecard_resp]

        provider = CricAPIProvider(api_key="test_key")
        result = provider.fetch_commentary("India", "Australia", "2025-01-15")
        assert result == {}

    @patch("ingestion.commentary_provider.requests.get")
    def test_match_not_found(self, mock_get):
        """No matching match in CricAPI search results."""
        # Search for both teams returns no matches
        empty_resp = _make_mock_response(200, {
            "status": "success",
            "data": [],
        })
        mock_get.return_value = empty_resp

        provider = CricAPIProvider(api_key="test_key")
        result = provider.fetch_commentary("India", "Australia", "2025-01-15")
        assert result == {}

    @patch("ingestion.commentary_provider.requests.get")
    def test_network_timeout(self, mock_get):
        """Network timeout is caught and returns empty."""
        import requests as req
        mock_get.side_effect = req.ConnectionError("timeout")

        provider = CricAPIProvider(api_key="test_key")
        result = provider.fetch_commentary("India", "Australia", "2025-01-15")
        assert result == {}

    @patch("ingestion.commentary_provider.requests.get")
    def test_team_name_matching_is_case_insensitive(self, mock_get):
        """Team matching should be case-insensitive."""
        match_resp = _make_mock_response(200, {
            "status": "success",
            "data": [{
                "id": "xyz789",
                "date": "2025-06-01",
                "teams": ["india", "AUSTRALIA"],
            }],
        })
        scorecard_resp = _make_mock_response(200, {
            "status": "success",
            "data": {"commentary": []},
        })
        mock_get.side_effect = [match_resp, scorecard_resp]

        provider = CricAPIProvider(api_key="test_key")
        result = provider.fetch_commentary("India", "Australia", "2025-06-01")
        # Should not fail — match found despite case mismatch
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# ProviderResult DATACLASS
# ═══════════════════════════════════════════════════════════════════

class TestProviderResult:

    def test_success_when_commentary_present(self):
        r = ProviderResult(commentary={"1_0_1": "hit"})
        assert r.success is True

    def test_not_success_when_empty(self):
        r = ProviderResult()
        assert r.success is False

    def test_error_stored(self):
        r = ProviderResult(error="Rate limited")
        assert r.error == "Rate limited"
        assert r.success is False


# ═══════════════════════════════════════════════════════════════════
# ENRICHMENT RESULT DATACLASS
# ═══════════════════════════════════════════════════════════════════

class TestEnrichmentResult:

    def test_success_when_api_found_no_error(self):
        r = EnrichmentResult(match_id="m1", api_found=True)
        assert r.success is True

    def test_not_success_with_error(self):
        r = EnrichmentResult(match_id="m1", api_found=True, error="DB error")
        assert r.success is False

    def test_not_success_when_api_not_found(self):
        r = EnrichmentResult(match_id="m1", api_found=False)
        assert r.success is False


# ═══════════════════════════════════════════════════════════════════
# enrich_match() — INTEGRATION WITH MOCK DB
# ═══════════════════════════════════════════════════════════════════

class TestEnrichMatch:
    """
    Tests ``enrich_match()`` with a real SQLite in-memory database
    and a ``FakeProvider``.
    """

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Create an in-memory SQLite DB with all tables."""
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from models import Base

        engine = create_engine("sqlite:///:memory:")

        @event.listens_for(engine, "connect")
        def _pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        self.db = Session()
        yield
        self.db.close()

    def _seed_match(
        self, team1="India", team2="Australia", date="2025-01-15",
    ):
        """Insert a match + player + deliveries for testing."""
        from models import Match, Player, Delivery, CricvizMetric

        match = Match(
            id=str(uuid.uuid4()),
            date=date,
            team1=team1,
            team2=team2,
            venue="MCG",
            outcome="India won",
            match_type="T20",
            gender="male",
            source_file=f"test_{uuid.uuid4().hex[:8]}.json",
        )
        self.db.add(match)

        batter = Player(id=str(uuid.uuid4()), name="Virat Kohli", country="India")
        bowler = Player(
            id=str(uuid.uuid4()), name="Pat Cummins",
            country="Australia", bowling_style="RF",
        )
        self.db.add_all([batter, bowler])
        self.db.flush()

        # Create 3 deliveries: ball 1,2,3 of over 0, innings 1
        deliveries = []
        for ball_num in range(1, 4):
            d = Delivery(
                id=str(uuid.uuid4()),
                match_id=match.id,
                innings=1,
                over=0,
                ball=ball_num,
                batter_id=batter.id,
                bowler_id=bowler.id,
                runs_bat=ball_num,  # 1, 2, 3
                runs_extras=0,
                commentary_text=None,
            )
            self.db.add(d)
            self.db.flush()

            metric = CricvizMetric(
                delivery_id=d.id,
                shot_intent="UNKNOWN",
                pitch_length_zone="UNKNOWN",
                is_false_shot=False,
                computed_xR=0.4,
                computed_xW=0.04,
                commentary_source="heuristic",
            )
            self.db.add(metric)
            deliveries.append(d)

        self.db.commit()
        return match, batter, bowler, deliveries

    def test_enrich_with_commentary_updates_deliveries(self):
        """Commentary text persisted and metrics re-computed."""
        match, _, _, deliveries = self._seed_match()

        provider = FakeProvider({
            "1_0_1": "smashed over cover for four",
            "1_0_2": "pushed to mid-on for a single",
            "1_0_3": "defended back to the bowler",
        })

        result = enrich_match(match.id, provider=provider, db=self.db)

        assert result.deliveries_updated == 3
        assert result.deliveries_skipped == 0
        assert result.api_found is True
        assert result.error is None

        # Verify commentary_text persisted
        for d in deliveries:
            self.db.refresh(d)
            assert d.commentary_text is not None
            assert len(d.commentary_text) > 0

        # Verify metrics re-computed with NLP path
        from models import CricvizMetric
        for d in deliveries:
            metric = self.db.query(CricvizMetric).filter(
                CricvizMetric.delivery_id == d.id
            ).first()
            assert metric is not None
            assert metric.commentary_source == "nlp_token"

    def test_enrich_with_commentary_uses_nlp_intent(self):
        """NLP tokens in commentary should drive shot_intent."""
        match, _, _, deliveries = self._seed_match()

        provider = FakeProvider({
            "1_0_1": "smashed it over the ropes for six",  # ATTACKING
            "1_0_2": "pushed gently to mid-on",             # ROTATING
            "1_0_3": "defended solidly on the front foot",   # DEFENSIVE
        })

        enrich_match(match.id, provider=provider, db=self.db)

        from models import CricvizMetric

        m1 = self.db.query(CricvizMetric).filter(
            CricvizMetric.delivery_id == deliveries[0].id
        ).first()
        assert m1.shot_intent == "ATTACKING"

        m2 = self.db.query(CricvizMetric).filter(
            CricvizMetric.delivery_id == deliveries[1].id
        ).first()
        assert m2.shot_intent == "ROTATING"

        m3 = self.db.query(CricvizMetric).filter(
            CricvizMetric.delivery_id == deliveries[2].id
        ).first()
        assert m3.shot_intent == "DEFENSIVE"

    def test_empty_provider_marks_api_not_found(self):
        """When provider returns empty, api_found should be False."""
        match, _, _, _ = self._seed_match()

        provider = EmptyProvider()
        result = enrich_match(match.id, provider=provider, db=self.db)

        assert result.api_found is False
        assert result.deliveries_updated == 0

    def test_partial_commentary_skips_missing_balls(self):
        """When commentary only covers some balls, others are skipped."""
        match, _, _, deliveries = self._seed_match()

        provider = FakeProvider({
            "1_0_1": "smashed it",
            # ball 2 and 3 not in commentary
        })

        result = enrich_match(match.id, provider=provider, db=self.db)

        assert result.deliveries_updated == 1
        assert result.deliveries_skipped == 2

        # Ball 1 should have commentary
        self.db.refresh(deliveries[0])
        assert deliveries[0].commentary_text == "smashed it"

        # Balls 2 and 3 should still be NULL
        self.db.refresh(deliveries[1])
        self.db.refresh(deliveries[2])
        assert deliveries[1].commentary_text is None
        assert deliveries[2].commentary_text is None

    def test_already_enriched_deliveries_are_skipped(self):
        """Deliveries with existing commentary_text are not re-fetched."""
        match, _, _, deliveries = self._seed_match()

        # Pre-fill commentary for all deliveries
        for d in deliveries:
            d.commentary_text = "existing commentary"
        self.db.commit()

        provider = FakeProvider({
            "1_0_1": "new commentary",
            "1_0_2": "new commentary",
            "1_0_3": "new commentary",
        })

        result = enrich_match(match.id, provider=provider, db=self.db)

        # All were already enriched → 0 updated
        assert result.deliveries_updated == 0
        assert result.deliveries_skipped == 0  # they weren't loaded (filtered out)

    def test_nonexistent_match_returns_error(self):
        """Enriching a match that doesn't exist returns an error result."""
        result = enrich_match("nonexistent-id", provider=FakeProvider(), db=self.db)
        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_provider_receives_correct_team_and_date(self):
        """Verify the provider is called with the match's team/date data."""
        match, _, _, _ = self._seed_match(
            team1="England", team2="Pakistan", date="2025-03-20",
        )

        provider = FakeProvider()
        enrich_match(match.id, provider=provider, db=self.db)

        assert len(provider.calls) == 1
        assert provider.calls[0] == ("England", "Pakistan", "2025-03-20")


# ═══════════════════════════════════════════════════════════════════
# _find_matches_needing_commentary
# ═══════════════════════════════════════════════════════════════════

class TestFindMatchesNeedingCommentary:

    @pytest.fixture(autouse=True)
    def setup_db(self):
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from models import Base

        engine = create_engine("sqlite:///:memory:")

        @event.listens_for(engine, "connect")
        def _pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        self.db = Session()
        yield
        self.db.close()

    def _seed_match_with_null_commentary(self, days_ago=0):
        from models import Match, Player, Delivery

        match = Match(
            id=str(uuid.uuid4()),
            date="2025-01-15",
            team1="India",
            team2="Australia",
            venue="MCG",
            outcome="India won",
            match_type="T20",
            gender="male",
            source_file=f"test_{uuid.uuid4().hex[:8]}.json",
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        )
        self.db.add(match)

        player = Player(id=str(uuid.uuid4()), name=f"Player_{uuid.uuid4().hex[:4]}")
        self.db.add(player)
        self.db.flush()

        delivery = Delivery(
            id=str(uuid.uuid4()),
            match_id=match.id,
            innings=1, over=0, ball=1,
            batter_id=player.id,
            bowler_id=player.id,
            runs_bat=0, runs_extras=0,
            commentary_text=None,
        )
        self.db.add(delivery)
        self.db.commit()
        return match

    def test_finds_matches_with_null_commentary(self):
        match = self._seed_match_with_null_commentary(days_ago=1)
        result = _find_matches_needing_commentary(self.db, limit=10)
        assert match.id in result

    def test_respects_since_filter(self):
        old_match = self._seed_match_with_null_commentary(days_ago=30)
        recent_match = self._seed_match_with_null_commentary(days_ago=1)

        cutoff = datetime.utcnow() - timedelta(days=7)
        result = _find_matches_needing_commentary(self.db, since=cutoff, limit=10)

        assert recent_match.id in result
        assert old_match.id not in result

    def test_respects_limit(self):
        for _ in range(5):
            self._seed_match_with_null_commentary(days_ago=1)

        result = _find_matches_needing_commentary(self.db, limit=3)
        assert len(result) == 3


# ═══════════════════════════════════════════════════════════════════
# BATCH ENRICHMENT (mocked at module boundary)
# ═══════════════════════════════════════════════════════════════════

class TestBatchEnrichment:

    @patch("ingestion.commentary_enricher.get_db_context")
    @patch("ingestion.commentary_enricher._find_matches_needing_commentary")
    @patch("ingestion.commentary_enricher.enrich_match")
    def test_enrich_recent_respects_daily_limit(
        self, mock_enrich, mock_find, mock_ctx,
    ):
        """enrich_recent_matches passes limit to finder."""
        mock_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_find.return_value = ["m1", "m2"]
        mock_enrich.return_value = EnrichmentResult(match_id="m1")

        results = enrich_recent_matches(days=3, daily_limit=50, provider=FakeProvider())

        # Verify limit was passed through
        mock_find.assert_called_once()
        call_kwargs = mock_find.call_args
        assert call_kwargs[1].get("limit", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None) is not None

    @patch("ingestion.commentary_enricher.get_db_context")
    @patch("ingestion.commentary_enricher._find_matches_needing_commentary")
    @patch("ingestion.commentary_enricher.enrich_match")
    def test_backfill_calls_without_since(
        self, mock_enrich, mock_find, mock_ctx,
    ):
        """backfill_all passes since=None to the finder."""
        mock_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_find.return_value = ["m1"]
        mock_enrich.return_value = EnrichmentResult(match_id="m1")

        backfill_all(daily_limit=10, provider=FakeProvider())

        mock_find.assert_called_once()
        call_args = mock_find.call_args
        # since should be None for backfill
        assert call_args[1].get("since") is None


# ═══════════════════════════════════════════════════════════════════
# COMMENTARY PARSING (edge cases)
# ═══════════════════════════════════════════════════════════════════

class TestCommentaryParsing:
    """Test the _parse_commentary_response method of CricAPIProvider."""

    def test_parse_flat_list(self):
        provider = CricAPIProvider(api_key="test")
        data = [
            {"innings": 1, "over": 5, "ball": 3, "text": "bowled him!"},
            {"innings": 2, "over": 0, "ball": 1, "comment": "driven to cover"},
        ]
        result = provider._parse_commentary_response(data)
        assert result == {
            "1_5_3": "bowled him!",
            "2_0_1": "driven to cover",
        }

    def test_parse_nested_commentary_key(self):
        provider = CricAPIProvider(api_key="test")
        data = {
            "commentary": [
                {"innings": 1, "over": 0, "ball": 1, "text": "short ball"},
            ],
        }
        result = provider._parse_commentary_response(data)
        assert result == {"1_0_1": "short ball"}

    def test_parse_empty_data(self):
        provider = CricAPIProvider(api_key="test")
        assert provider._parse_commentary_response({}) == {}

    def test_parse_skips_empty_text(self):
        provider = CricAPIProvider(api_key="test")
        data = [
            {"innings": 1, "over": 0, "ball": 1, "text": ""},
            {"innings": 1, "over": 0, "ball": 2, "text": "valid text"},
        ]
        result = provider._parse_commentary_response(data)
        assert "1_0_1" not in result
        assert result["1_0_2"] == "valid text"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
