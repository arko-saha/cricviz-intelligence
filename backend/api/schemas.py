"""
Pydantic v2 schemas — Section 4.

All request/response shapes for the API layer.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Requests ─────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    source: str = Field(..., min_length=1, description="Local path or URL to Cricsheet ZIP/CSV")
    event_filter: Optional[str] = Field(None, description="Substring match for tournament event.name")



# ── Responses ────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    job_id: str
    status: str


class MatchSummary(BaseModel):
    id: str
    date: str
    team1: str
    team2: str
    venue: str
    outcome: str
    match_type: str
    gender: str


class MatchListResponse(BaseModel):
    matches: List[MatchSummary]
    total: int
    page: int
    limit: int


class DeliveryRow(BaseModel):
    id: str
    innings: int
    over: int
    ball: int
    batter: str
    bowler: str
    runs_bat: int
    runs_extras: int
    wicket_type: Optional[str] = None
    shot_intent: str = "UNKNOWN"
    pitch_zone: str = "UNKNOWN"
    is_false_shot: bool = False
    xR: float = 0.0
    xW: float = 0.0


class DeliveryListResponse(BaseModel):
    match_id: str
    deliveries: List[DeliveryRow]
    total: int


class PlayerProfile(BaseModel):
    id: str
    name: str
    handedness: Optional[str] = None
    bowling_style: Optional[str] = None
    country: Optional[str] = None


class IntentDistribution(BaseModel):
    intent: str
    count: int


class ZoneDistribution(BaseModel):
    zone: str
    count: int


class PlayerProfileResponse(BaseModel):
    player: PlayerProfile
    total_deliveries_faced: int
    avg_xR: float
    avg_xW: float
    false_shot_pct: float
    dominant_shot_intent: str
    dominant_pitch_zone: str
    shot_intent_distribution: List[IntentDistribution]
    pitch_zone_distribution: List[ZoneDistribution]


class WormDataPoint(BaseModel):
    over: int
    innings1_runs: int
    innings2_runs: int
    innings1_wickets: int
    innings2_wickets: int
    innings1_marginal_runs: int
    innings2_marginal_runs: int


class WormResponse(BaseModel):
    match_id: str
    team1: str
    team2: str
    data: List[WormDataPoint]


class StatsResponse(BaseModel):
    matches: int
    players: int
    deliveries: int
    enriched_metrics: int


class HealthResponse(BaseModel):
    status: str
    db: str
    version: str


class JobStatusResponse(BaseModel):
    status: str
    matches_processed: int = 0
    matches_failed: int = 0
    total_deliveries: int = 0
    logs: list = []


class AIInsightRequest(BaseModel):
    context_data: dict
    context_type: str = "match"  # "match", "player", or "over"


class AIInsightResponse(BaseModel):
    insight: str
    model_used: str
    attempt: int
    status: str


class MLStatusResponse(BaseModel):
    xr_model_loaded: bool
    xw_model_loaded: bool
    model_type: Optional[str] = None
    training_date: Optional[str] = None
    sample_size: Optional[int] = None
    train_size: Optional[int] = None
    test_size: Optional[int] = None
    features: Optional[List[str]] = None
    xr_evaluation: Optional[dict] = None
    xw_evaluation: Optional[dict] = None


class RetrainResponse(BaseModel):
    status: str
    message: str = ""


# ── Global Search ────────────────────────────────────────────────

class PlayerSearchResult(BaseModel):
    id: str
    name: str
    country: Optional[str] = None

class MatchSearchResult(BaseModel):
    id: str
    team1: str
    team2: str
    date: str
    venue: str

class GlobalSearchResponse(BaseModel):
    players: List[PlayerSearchResult]
    matches: List[MatchSearchResult]


# ── Commentary Enrichment ────────────────────────────────────────

class CommentaryEnrichRequest(BaseModel):
    match_id: Optional[str] = Field(
        None,
        description="Enrich a specific match.  If omitted, enriches recent matches.",
    )
    days: Optional[int] = Field(
        None, ge=1, le=365,
        description="Lookback window in days (ignored when match_id is set).",
    )
    limit: Optional[int] = Field(
        None, ge=1, le=500,
        description="Max matches to process (ignored when match_id is set).",
    )


class CommentaryEnrichMatchResult(BaseModel):
    match_id: str
    team1: str = ""
    team2: str = ""
    deliveries_updated: int = 0
    deliveries_skipped: int = 0
    api_found: bool = False
    error: Optional[str] = None


class CommentaryEnrichResponse(BaseModel):
    status: str
    results: List[CommentaryEnrichMatchResult]
    total_updated: int = 0
