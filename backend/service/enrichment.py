"""
CricViz Enrichment Engine — Section 3.

Pure, stateless function module. No DB calls, no HTTP calls.
Every function takes a delivery dict (and optional commentary) and returns
a computed metric. Fully unit-testable in isolation.
"""
from typing import Dict, Any
import os
import logging
import pandas as pd
import joblib

logger = logging.getLogger("cricviz.enrichment")

# Load ML models globally at module startup if they exist
MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "models")
XR_MODEL_PATH = os.path.join(MODELS_DIR, "xR_model.pkl")
XW_MODEL_PATH = os.path.join(MODELS_DIR, "xW_model.pkl")

xr_model = None
xw_model = None

try:
    if os.path.exists(XR_MODEL_PATH):
        xr_model = joblib.load(XR_MODEL_PATH)
        logger.info("Loaded xR model from disk.")
except Exception as e:
    logger.warning(f"Could not load xR model: {e}")

try:
    if os.path.exists(XW_MODEL_PATH):
        xw_model = joblib.load(XW_MODEL_PATH)
        logger.info("Loaded xW model from disk.")
except Exception as e:
    logger.warning(f"Could not load xW model: {e}")


# ═══════════════════════════════════════════════════════════════════
# SHOT INTENT
# ═══════════════════════════════════════════════════════════════════

# Priority-ordered list of (intent, token_set) tuples.
# Extensible without restructuring — just add tokens to the set.
_INTENT_TOKENS = [
    ("ATTACKING", {
        "six", "four", "smashed", "heaved", "slapped", "slog",
        "pulled", "hooked", "lofted", "blasted", "maximum",
    }),
    ("ROTATING", {
        "pushed", "nudged", "glanced", "tickled", "worked",
        "clipped", "flicked", "dabbed", "guided", "ran",
    }),
    ("DEFENSIVE", {
        "defended", "blocked", "padded", "left", "shouldered",
    }),
]


def compute_shot_intent(delivery: dict, commentary: str = "") -> str:
    """
    Returns: "ATTACKING" | "ROTATING" | "DEFENSIVE" | "UNKNOWN"

    Uses a priority-ordered list of (intent, token_set) tuples.
    Falls back to runs-based inference when commentary is empty.
    """
    if not isinstance(commentary, str):
        commentary = ""

    lower_comm = commentary.lower()

    # Token-based matching (priority order)
    if lower_comm.strip():
        for intent, tokens in _INTENT_TOKENS:
            for token in tokens:
                if token in lower_comm:
                    return intent

    # Runs-based fallback (when no commentary available)
    try:
        if "runs" in delivery and isinstance(delivery["runs"], dict):
            batter_runs = delivery["runs"].get("batter", 0) or 0
        else:
            batter_runs = int(delivery.get("runs_bat", 0) or 0)

        if batter_runs >= 4:
            return "ATTACKING"
        elif batter_runs == 1 or batter_runs == 2:
            return "ROTATING"
        elif batter_runs == 0:
            return "DEFENSIVE"
    except (TypeError, ValueError, AttributeError):
        pass

    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════
# PITCH ZONE
# ═══════════════════════════════════════════════════════════════════

# Priority-ordered: BOUNCER > YORKER checked before FULL > SHORT.
_ZONE_TOKENS = [
    ("BOUNCER", {"bouncer", "beamer"}),
    ("YORKER",  {"yorker", "full toss", "toe-crusher"}),
    ("FULL",    {"full", "overpitched", "half-volley"}),
    ("SHORT",   {"short", "short-pitched", "pulled", "bounced"}),
]

_GOOD_LENGTH_PACE = {"RF", "RFM", "LF", "LFM", "MF", "RMF", "LMF"}
_GOOD_LENGTH_SPIN_TOKENS = {"tossed up", "flighted"}


def compute_pitch_zone(
    delivery: dict,
    commentary: str = "",
    bowler_style: str = "",
) -> str:
    """
    Returns: "YORKER" | "FULL" | "GOOD_LENGTH" | "SHORT" | "BOUNCER" | "UNKNOWN"
    """
    if not isinstance(commentary, str):
        commentary = ""
    if not isinstance(bowler_style, str):
        bowler_style = ""

    lower_comm = commentary.lower()

    # Token-based matching (BOUNCER/YORKER before FULL/SHORT)
    if lower_comm.strip():
        for zone, tokens in _ZONE_TOKENS:
            for token in tokens:
                if token in lower_comm:
                    return zone

        # GOOD_LENGTH for spin with flight tokens
        for token in _GOOD_LENGTH_SPIN_TOKENS:
            if token in lower_comm:
                return "GOOD_LENGTH"

    # Default GOOD_LENGTH for pace bowlers when no other token matched
    if bowler_style.upper() in _GOOD_LENGTH_PACE:
        return "GOOD_LENGTH"

    # Heuristic fallback based on runs + wicket
    try:
        if "runs" in delivery and isinstance(delivery["runs"], dict):
            batter_runs = delivery["runs"].get("batter", 0) or 0
        else:
            batter_runs = int(delivery.get("runs_bat", 0) or 0)

        wickets = delivery.get("wickets", [])
        has_wicket = bool(wickets) or bool(delivery.get("wicket_type"))

        if has_wicket and batter_runs == 0:
            return "GOOD_LENGTH"
        if batter_runs >= 4:
            return "SHORT"  # Boundaries more likely off short/full
    except (TypeError, ValueError, AttributeError):
        pass

    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════
# FALSE SHOT
# ═══════════════════════════════════════════════════════════════════

_FALSE_SHOT_TOKENS = {
    "edged", "outside edge", "inside edge",
    "play and miss", "beaten", "dropped",
}


def compute_false_shot(delivery: dict, commentary: str = "") -> bool:
    """
    Returns True if the delivery represents a false shot.
    Never raises — wraps in try/except, returns False on any unexpected input.
    """
    try:
        if not isinstance(commentary, str):
            commentary = ""
        if not isinstance(delivery, dict):
            return False

        lower_comm = commentary.lower()

        # Check 1: Wicket (not run out)
        wickets = delivery.get("wickets", [])
        if wickets and isinstance(wickets, list):
            for w in wickets:
                kind = w.get("kind", "").lower() if isinstance(w, dict) else ""
                if kind and kind != "run out":
                    return True

        # Also check flat wicket_type field (CSV format)
        wt = delivery.get("wicket_type")
        if wt and isinstance(wt, str) and wt.lower() not in ("", "run out"):
            return True

        # Check 2: Edge tokens in commentary
        for token in _FALSE_SHOT_TOKENS:
            if token in lower_comm:
                return True

        # Check 3: No-ball with "missed"
        extras = delivery.get("extras", {})
        if isinstance(extras, dict) and extras.get("noballs") and "missed" in lower_comm:
            return True

        return False

    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# EXPECTED RUNS (xR) — Deterministic Lookup
# ═══════════════════════════════════════════════════════════════════

# Full 4×6 intent × zone matrix (intent → zone → base xR)
_XR_TABLE: Dict[str, Dict[str, float]] = {
    "ATTACKING": {
        "YORKER":      0.40,
        "FULL":        1.80,
        "GOOD_LENGTH": 0.90,
        "SHORT":       1.20,
        "BOUNCER":     0.60,
        "UNKNOWN":     0.80,
    },
    "ROTATING": {
        "YORKER":      0.20,
        "FULL":        0.50,
        "GOOD_LENGTH": 0.35,
        "SHORT":       0.45,
        "BOUNCER":     0.30,
        "UNKNOWN":     0.35,
    },
    "DEFENSIVE": {
        "YORKER":      0.10,
        "FULL":        0.08,
        "GOOD_LENGTH": 0.05,
        "SHORT":       0.15,
        "BOUNCER":     0.12,
        "UNKNOWN":     0.08,
    },
    "UNKNOWN": {
        "YORKER":      0.25,
        "FULL":        0.60,
        "GOOD_LENGTH": 0.40,
        "SHORT":       0.55,
        "BOUNCER":     0.35,
        "UNKNOWN":     0.40,
    },
}


def compute_xR(
    delivery: dict,
    shot_intent: str,
    pitch_zone: str,
    is_false_shot: bool,
    innings: int = 1,
    over_number: int = 0,
    runs_in_over_so_far: int = 0,
    wickets_in_innings: int = 0,
) -> float:
    """
    Returns expected runs. Uses scikit-learn model if available,
    otherwise falls back to deterministic lookup table.
    """
    if xr_model is not None:
        try:
            df = pd.DataFrame([{
                "shot_intent": shot_intent,
                "pitch_length_zone": pitch_zone,
                "is_false_shot": int(is_false_shot),
                "innings": innings,
                "over": over_number,
                "runs_in_over_so_far": runs_in_over_so_far,
                "wickets_in_innings": wickets_in_innings
            }])
            pred = float(xr_model.predict(df)[0])
            # Cap outputs
            return round(max(0.0, min(pred, 6.0)), 4)
        except Exception as e:
            logger.warning(f"xR inference failed: {e}. Falling back to heuristics.")

    # Fallback
    intent_row = _XR_TABLE.get(shot_intent, _XR_TABLE["UNKNOWN"])
    base = intent_row.get(pitch_zone, intent_row.get("UNKNOWN", 0.4))

    if is_false_shot:
        base *= 0.6

    return round(base, 4)


# ═══════════════════════════════════════════════════════════════════
# EXPECTED WICKETS (xW) — Deterministic Lookup
# ═══════════════════════════════════════════════════════════════════

# Full 4×6 intent × zone matrix (intent → zone → base xW)
_XW_TABLE: Dict[str, Dict[str, float]] = {
    "ATTACKING": {
        "YORKER":      0.12,
        "FULL":        0.04,
        "GOOD_LENGTH": 0.06,
        "SHORT":       0.05,
        "BOUNCER":     0.08,
        "UNKNOWN":     0.05,
    },
    "ROTATING": {
        "YORKER":      0.06,
        "FULL":        0.02,
        "GOOD_LENGTH": 0.03,
        "SHORT":       0.03,
        "BOUNCER":     0.04,
        "UNKNOWN":     0.03,
    },
    "DEFENSIVE": {
        "YORKER":      0.08,
        "FULL":        0.03,
        "GOOD_LENGTH": 0.02,
        "SHORT":       0.02,
        "BOUNCER":     0.03,
        "UNKNOWN":     0.03,
    },
    "UNKNOWN": {
        "YORKER":      0.08,
        "FULL":        0.03,
        "GOOD_LENGTH": 0.04,
        "SHORT":       0.04,
        "BOUNCER":     0.05,
        "UNKNOWN":     0.04,
    },
}


def compute_xW(
    delivery: dict,
    shot_intent: str,
    pitch_zone: str,
    is_false_shot: bool,
    innings: int = 1,
    over_number: int = 0,
    runs_in_over_so_far: int = 0,
    wickets_in_innings: int = 0,
) -> float:
    """
    Returns expected wicket probability. Uses scikit-learn model if available,
    otherwise falls back to deterministic lookup table.
    """
    if xw_model is not None:
        try:
            df = pd.DataFrame([{
                "shot_intent": shot_intent,
                "pitch_length_zone": pitch_zone,
                "is_false_shot": int(is_false_shot),
                "innings": innings,
                "over": over_number,
                "runs_in_over_so_far": runs_in_over_so_far,
                "wickets_in_innings": wickets_in_innings
            }])
            pred = float(xw_model.predict(df)[0])
            # Cap outputs
            return round(max(0.0, min(pred, 1.0)), 4)
        except Exception as e:
            logger.warning(f"xW inference failed: {e}. Falling back to heuristics.")

    # Fallback
    intent_row = _XW_TABLE.get(shot_intent, _XW_TABLE["UNKNOWN"])
    base = intent_row.get(pitch_zone, intent_row.get("UNKNOWN", 0.04))

    if is_false_shot:
        base *= 1.8

    return round(min(base, 1.0), 4)


# ═══════════════════════════════════════════════════════════════════
# CONVENIENCE: Enrich a single delivery
# ═══════════════════════════════════════════════════════════════════

def enrich_delivery(
    delivery: dict,
    commentary: str = "",
    bowler_style: str = "",
    innings: int = 1,
    over_number: int = 0,
    runs_in_over_so_far: int = 0,
    wickets_in_innings: int = 0,
) -> Dict[str, Any]:
    """
    Runs all five enrichment functions on a delivery dict.
    Returns a dict ready to be stored as CricvizMetric fields.
    """
    intent = compute_shot_intent(delivery, commentary)
    zone = compute_pitch_zone(delivery, commentary, bowler_style)
    false_shot = compute_false_shot(delivery, commentary)
    xr = compute_xR(
        delivery, intent, zone, false_shot,
        innings, over_number, runs_in_over_so_far, wickets_in_innings
    )
    xw = compute_xW(
        delivery, intent, zone, false_shot,
        innings, over_number, runs_in_over_so_far, wickets_in_innings
    )

    source = "nlp_token" if commentary and isinstance(commentary, str) and commentary.strip() else "heuristic"

    return {
        "shot_intent": intent,
        "pitch_length_zone": zone,
        "is_false_shot": false_shot,
        "computed_xR": xr,
        "computed_xW": xw,
        "commentary_source": source,
    }
