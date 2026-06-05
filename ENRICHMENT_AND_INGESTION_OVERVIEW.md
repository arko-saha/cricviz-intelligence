# Enrichment and Ingestion Interface Summary

## 1. `enrichment.py` interface

### Shot Intent
- Function: `compute_shot_intent(delivery: dict, commentary: str = "") -> str`
- Inputs:
  - `delivery`: dict representing a delivery
  - `commentary`: optional string
- Returns:
  - `"ATTACKING"`, `"ROTATING"`, `"DEFENSIVE"`, or `"UNKNOWN"`
- Logic:
  - Attempts priority token matching on lowercase commentary using `_INTENT_TOKENS`
  - Fallback heuristic begins when commentary has no matching token or is empty:
    - reads batter runs from `delivery["runs"]["batter"]` or `delivery["runs_bat"]`
    - `>= 4` → `ATTACKING`
    - `1` or `2` → `ROTATING`
    - `0` → `DEFENSIVE`
    - any invalid input → `UNKNOWN`

### Pitch Zone
- Function: `compute_pitch_zone(delivery: dict, commentary: str = "", bowler_style: str = "") -> str`
- Inputs:
  - `delivery`: dict
  - `commentary`: optional string
  - `bowler_style`: optional string
- Returns:
  - `"YORKER"`, `"FULL"`, `"GOOD_LENGTH"`, `"SHORT"`, `"BOUNCER"`, or `"UNKNOWN"`
- Logic:
  - Attempts token matching on commentary using `_ZONE_TOKENS` in priority order
  - Checks spin commentary tokens via `_GOOD_LENGTH_SPIN_TOKENS` for `GOOD_LENGTH`
  - Defaults to `GOOD_LENGTH` when `bowler_style` is one of `_GOOD_LENGTH_PACE`
  - Heuristic fallback begins if no commentary/mode match:
    - reads batter runs from `delivery["runs"]["batter"]` or `delivery["runs_bat"]`
    - detects wickets via `delivery["wickets"]` or `delivery["wicket_type"]`
    - if wicket present and batter_runs == 0 → `GOOD_LENGTH`
    - if batter_runs >= 4 → `SHORT`
    - otherwise `UNKNOWN`

### False Shot
- Function: `compute_false_shot(delivery: dict, commentary: str = "") -> bool`
- Inputs:
  - `delivery`: dict
  - `commentary`: optional string
- Returns:
  - `True` or `False`
- Logic:
  - `True` if any of:
    - `delivery["wickets"]` contains a wicket with kind not equal to `"run out"`
    - `delivery["wicket_type"]` exists and is not `"run out"`
    - commentary contains any token from `_FALSE_SHOT_TOKENS`
    - extras dict has `noballs` and commentary contains `"missed"`
  - Returns `False` on invalid input or exception

### xR / xW interface
- Functions:
  - `compute_xR(delivery, shot_intent, pitch_zone, is_false_shot, innings=1, over_number=0, runs_in_over_so_far=0, wickets_in_innings=0) -> float`
  - `compute_xW(delivery, shot_intent, pitch_zone, is_false_shot, innings=1, over_number=0, runs_in_over_so_far=0, wickets_in_innings=0) -> float`
- Inputs:
  - `delivery`: dict
  - `shot_intent`: string category
  - `pitch_zone`: string category
  - `is_false_shot`: bool
  - `innings`: int
  - `over_number`: int
  - `runs_in_over_so_far`: int
  - `wickets_in_innings`: int
- Returns:
  - `float`
- Logic:
  - If model file exists in `backend/ml/models`, uses a pandas DataFrame with columns:
    - `shot_intent`
    - `pitch_length_zone`
    - `is_false_shot`
    - `innings`
    - `over`
    - `runs_in_over_so_far`
    - `wickets_in_innings`
  - Otherwise fallback begins inside the same function and uses deterministic lookup tables `_XR_TABLE` / `_XW_TABLE`
  - False shot adjustments:
    - `compute_xR`: multiply base by `0.6` when `is_false_shot` is `True`
    - `compute_xW`: multiply base by `1.8` when `is_false_shot` is `True`

### Convenience wrapper
- Function: `enrich_delivery(...) -> Dict[str, Any]`
- Calls:
  - `compute_shot_intent`
  - `compute_pitch_zone`
  - `compute_false_shot`
  - `compute_xR`
  - `compute_xW`
- Returns a dict with fields ready for `CricvizMetric`, including `commentary_source` set to `nlp_token` when commentary exists, otherwise `heuristic`

## 2. Current player upsert logic

### Source
- Implemented in `backend/repository/player_repo.py`
- Used by ingestion service in `backend/service/ingestion_service.py`

### Match key
- Exact lookup key:
  - `Player.name`
  - `Player.country` when provided
- Behavior:
  - If `name` is empty returns `None`
  - Strip whitespace from `name`
  - Query exact match on `Player.name`
  - If `country` provided, also filter by `Player.country`
  - If exact match exists, return it
  - Otherwise attempt fuzzy matching on cached names for the same `country` (or all names if `country` omitted)
  - If fuzzy match score >= 85, use that matched record
  - Otherwise create a new `Player`

### Database uniqueness
- `Player` model defines:
  - `UniqueConstraint("name", "country", name="uq_player_name_country")`
- Effective DB match key is `(name, country)`

## 3. Shape of the xR / xW lookup

### Data structure
- Deterministic lookup shape:
  - `_XR_TABLE`: `Dict[str, Dict[str, float]]`
  - `_XW_TABLE`: `Dict[str, Dict[str, float]]`

### Dimensions
- First dimension: `shot_intent`
  - `"ATTACKING"`
  - `"ROTATING"`
  - `"DEFENSIVE"`
  - `"UNKNOWN"`
- Second dimension: `pitch_zone`
  - `"YORKER"`
  - `"FULL"`
  - `"GOOD_LENGTH"`
  - `"SHORT"`
  - `"BOUNCER"`
  - `"UNKNOWN"`

### Model vs lookup
- If ML model files are present, `compute_xR` / `compute_xW` use a pandas DataFrame and `model.predict(...)`
- If no model or inference fails, fallback uses the nested dict lookup plus false-shot multiplier
- The deterministic lookup depends only on:
  - `shot_intent`
  - `pitch_zone`
  - `is_false_shot` (via multiplier)
