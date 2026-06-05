"""
Enrichment Engine Unit Tests — Section 3 contract.

Each function tested with at least 3 inputs:
  - Normal case
  - Empty string / missing data
  - Conflicting tokens (e.g., 'short full toss')

Also tests:
  - compute_false_shot with run-out → returns False
  - compute_xR / compute_xW with false_shot multiplier
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from service.enrichment import (
    compute_shot_intent,
    compute_pitch_zone,
    compute_false_shot,
    compute_xR,
    compute_xW,
    enrich_delivery,
)


class TestShotIntent:
    def test_attacking_from_commentary(self):
        d = {"runs": {"batter": 4}}
        assert compute_shot_intent(d, "he smashed it over cover") == "ATTACKING"

    def test_rotating_from_commentary(self):
        d = {"runs": {"batter": 1}}
        assert compute_shot_intent(d, "pushed into the gap and ran") == "ROTATING"

    def test_defensive_from_commentary(self):
        d = {"runs": {"batter": 0}}
        assert compute_shot_intent(d, "defended solidly") == "DEFENSIVE"

    def test_empty_commentary_fallback_attacking(self):
        d = {"runs": {"batter": 6}}
        assert compute_shot_intent(d, "") == "ATTACKING"

    def test_empty_commentary_fallback_rotating(self):
        d = {"runs": {"batter": 1}}
        assert compute_shot_intent(d, "") == "ROTATING"

    def test_empty_commentary_fallback_defensive(self):
        d = {"runs": {"batter": 0}}
        assert compute_shot_intent(d, "") == "DEFENSIVE"

    def test_none_commentary(self):
        d = {"runs": {"batter": 4}}
        assert compute_shot_intent(d, None) == "ATTACKING"

    def test_conflicting_tokens_priority(self):
        """'lofted' (ATTACKING) should win over 'pushed' (ROTATING) due to priority"""
        d = {"runs": {"batter": 4}}
        assert compute_shot_intent(d, "lofted and pushed") == "ATTACKING"

    def test_csv_format(self):
        d = {"runs_bat": 4}
        assert compute_shot_intent(d, "") == "ATTACKING"


class TestPitchZone:
    def test_bouncer_from_commentary(self):
        d = {}
        assert compute_pitch_zone(d, "short bouncer, ducked under") == "BOUNCER"

    def test_yorker_from_commentary(self):
        d = {}
        assert compute_pitch_zone(d, "perfect yorker at the base") == "YORKER"

    def test_full_toss_classified_as_yorker(self):
        """'full toss' should match YORKER, not FULL (priority ordering)"""
        d = {}
        assert compute_pitch_zone(d, "full toss down leg") == "YORKER"

    def test_short_full_toss_conflict(self):
        """'short full toss' — BOUNCER/YORKER checked first; 'full toss' matches YORKER"""
        d = {}
        result = compute_pitch_zone(d, "short full toss")
        assert result in ("YORKER", "SHORT")  # depends on order in text

    def test_empty_commentary_pace_bowler(self):
        d = {}
        assert compute_pitch_zone(d, "", "RF") == "GOOD_LENGTH"

    def test_empty_commentary_unknown_bowler(self):
        d = {"runs": {"batter": 0}}
        result = compute_pitch_zone(d, "", "")
        assert result in ("UNKNOWN", "GOOD_LENGTH")

    def test_spin_flight_tokens(self):
        d = {}
        assert compute_pitch_zone(d, "tossed up nicely", "OB") == "GOOD_LENGTH"


class TestFalseShot:
    def test_wicket_caught(self):
        d = {"wickets": [{"kind": "caught"}]}
        assert compute_false_shot(d, "") is True

    def test_run_out_not_false_shot(self):
        d = {"wickets": [{"kind": "run out"}]}
        assert compute_false_shot(d, "") is False

    def test_edge_in_commentary(self):
        d = {}
        assert compute_false_shot(d, "outside edge, just short of slip") is True

    def test_play_and_miss(self):
        d = {}
        assert compute_false_shot(d, "play and miss, beaten all ends up") is True

    def test_clean_hit_no_false_shot(self):
        d = {"runs": {"batter": 4}}
        assert compute_false_shot(d, "drives through cover") is False

    def test_empty_delivery(self):
        assert compute_false_shot({}, "") is False

    def test_none_commentary(self):
        assert compute_false_shot({}, None) is False

    def test_noball_with_missed(self):
        d = {"extras": {"noballs": 1}}
        assert compute_false_shot(d, "no ball, missed completely") is True

    def test_csv_wicket_type(self):
        d = {"wicket_type": "bowled"}
        assert compute_false_shot(d, "") is True

    def test_csv_run_out(self):
        d = {"wicket_type": "run out"}
        assert compute_false_shot(d, "") is False


class TestXR:
    def setup_method(self):
        from service import enrichment
        self.old_predictor = enrichment.predictor.predict_xR
        enrichment.predictor.predict_xR = lambda *args, **kwargs: -1.0
        
    def teardown_method(self):
        from service import enrichment
        enrichment.predictor.predict_xR = self.old_predictor

    def test_attacking_full(self):
        result = compute_xR({}, "ATTACKING", "FULL", False)
        assert result == 1.8

    def test_defensive_good_length(self):
        result = compute_xR({}, "DEFENSIVE", "GOOD_LENGTH", False)
        assert result == 0.05

    def test_false_shot_penalty(self):
        without = compute_xR({}, "ATTACKING", "FULL", False)
        with_fs = compute_xR({}, "ATTACKING", "FULL", True)
        assert with_fs == round(without * 0.6, 4)

    def test_unknown_intent_zone(self):
        result = compute_xR({}, "UNKNOWN", "UNKNOWN", False)
        assert result == 0.4


class TestXW:
    def setup_method(self):
        from service import enrichment
        self.old_predictor = enrichment.predictor.predict_xW
        enrichment.predictor.predict_xW = lambda *args, **kwargs: -1.0
        
    def teardown_method(self):
        from service import enrichment
        enrichment.predictor.predict_xW = self.old_predictor

    def test_attacking_yorker(self):
        result = compute_xW({}, "ATTACKING", "YORKER", False)
        assert result == 0.12

    def test_defensive_good_length(self):
        result = compute_xW({}, "DEFENSIVE", "GOOD_LENGTH", False)
        assert result == 0.02

    def test_false_shot_multiplier(self):
        without = compute_xW({}, "ATTACKING", "YORKER", False)
        with_fs = compute_xW({}, "ATTACKING", "YORKER", True)
        expected = round(min(without * 1.8, 1.0), 4)
        assert with_fs == expected

    def test_cap_at_one(self):
        """Even extreme values should be capped at 1.0"""
        result = compute_xW({}, "ATTACKING", "YORKER", True)
        assert result <= 1.0


class TestEnrichDelivery:
    def test_full_enrichment(self):
        d = {"runs": {"batter": 4, "extras": 0, "total": 4}}
        result = enrich_delivery(d, "smashed over cover", "RF")
        assert result["shot_intent"] == "ATTACKING"
        assert "computed_xR" in result
        assert "computed_xW" in result
        assert isinstance(result["is_false_shot"], bool)

    def test_empty_delivery(self):
        result = enrich_delivery({})
        assert result["shot_intent"] in ("DEFENSIVE", "UNKNOWN")
        assert result["computed_xR"] >= 0
        assert result["computed_xW"] >= 0

    def test_pass_through_enrichment(self):
        d = {"runs": {"batter": 6, "extras": 0, "total": 6}}
        commentary_text = "He lofts it over long-on for a maximum! Brilliant shot, hit right out of the middle."
        result = enrich_delivery(d, commentary_text, "RF")
        assert result["shot_intent"] == "ATTACKING"
        assert result["is_false_shot"] is False
        assert result["commentary_source"] == "nlp_token"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
