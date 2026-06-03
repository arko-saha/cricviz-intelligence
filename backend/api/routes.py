"""
FastAPI Routes — Section 4.

All route handlers use async def with response_model declarations.
No business logic inside routes — all delegated to Service layer.
HTTPException handlers for 404, 422, 500.
"""
import logging
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db, engine
from config import API_VERSION
from service import match_service, ingestion_service
from ingestion.parser import run_ingestion
from ingestion.csv_loader import run_csv_ingestion
from api.schemas import (
    IngestRequest, IngestResponse,
    MatchListResponse,
    DeliveryListResponse, DeliveryRow,
    PlayerProfileResponse,
    WormResponse, WormDataPoint,
    StatsResponse, HealthResponse,
    JobStatusResponse,
    AIInsightRequest, AIInsightResponse,
    MLStatusResponse,
    GlobalSearchResponse,
)
from api.auth import (
    get_password_hash, verify_password, create_access_token, get_current_user
)
from models import User

logger = logging.getLogger("cricviz.api")

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════

from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str
    password: str

@router.post("/auth/register", response_model=Token)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new admin user."""
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    
    access_token = create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate and return JWT token."""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


# ═══════════════════════════════════════════════════════════════════
# POST /ingest
# ═══════════════════════════════════════════════════════════════════

@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    body: IngestRequest,
):
    """Trigger ingestion pipeline asynchronously via Celery."""
    source = body.source.strip()
    if not source:
        raise HTTPException(status_code=422, detail="Source must not be empty")

    job_id = ingestion_service.create_job()

    from worker import run_zip_ingestion_task, run_csv_ingestion_task

    # Detect CSV vs ZIP and dispatch accordingly
    if source.lower().endswith(".csv"):
        run_csv_ingestion_task.delay(source, job_id)
    else:
        run_zip_ingestion_task.delay(source, job_id)

    return IngestResponse(job_id=job_id, status="queued")


# ═══════════════════════════════════════════════════════════════════
# GET /ingest/status/{job_id}
# ═══════════════════════════════════════════════════════════════════

@router.get("/ingest/status/{job_id}", response_model=JobStatusResponse)
async def ingest_status(job_id: str):
    """Get the current status of an ingestion job."""
    job = ingestion_service.get_job(job_id)
    if job.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)


# ═══════════════════════════════════════════════════════════════════
# GET /matches
# ═══════════════════════════════════════════════════════════════════

@router.get("/matches", response_model=MatchListResponse)
async def list_matches(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    team: Optional[str] = Query(None, description="Filter by team name"),
    venue: Optional[str] = Query(None, description="Filter by venue"),
    year: Optional[str] = Query(None, description="Filter by match year (YYYY)"),
    gender: Optional[str] = Query(None, description="Filter by gender (male, female)"),
    db: Session = Depends(get_db),
):
    """Returns paginated match list with optional filtering."""
    try:
        result = match_service.get_matches(db, page, limit, team, venue, year, gender)
        return MatchListResponse(**result)
    except Exception as e:
        logger.exception("Error listing matches")
        raise HTTPException(status_code=500, detail="Internal server error")


# ═══════════════════════════════════════════════════════════════════
# GET /matches/{match_id}/deliveries
# ═══════════════════════════════════════════════════════════════════

@router.get("/matches/{match_id}/deliveries", response_model=DeliveryListResponse)
async def match_deliveries(
    match_id: str,
    innings: int = Query(None, ge=1, le=4),
    over: int = Query(None, ge=0, le=50),
    db: Session = Depends(get_db),
):
    """Returns all deliveries for a match with enriched CricViz metrics."""
    try:
        deliveries = match_service.get_match_deliveries(db, match_id, innings, over)
        if deliveries is None:
            raise HTTPException(status_code=404, detail="Match not found")
        return DeliveryListResponse(
            match_id=match_id,
            deliveries=[DeliveryRow(**d) for d in deliveries],
            total=len(deliveries),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching deliveries")
        raise HTTPException(status_code=500, detail="Internal server error")


# ═══════════════════════════════════════════════════════════════════
# GET /players/{player_id}/profile
# ═══════════════════════════════════════════════════════════════════

@router.get("/players/{player_id}/profile", response_model=PlayerProfileResponse)
async def player_profile(
    player_id: str,
    db: Session = Depends(get_db),
):
    """Returns player identity + aggregated CricViz metrics."""
    try:
        profile = match_service.get_player_profile(db, player_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Player not found")
        return PlayerProfileResponse(**profile)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching player profile")
        raise HTTPException(status_code=500, detail="Internal server error")


# ═══════════════════════════════════════════════════════════════════
# GET /analytics/match/{match_id}/worm
# ═══════════════════════════════════════════════════════════════════

@router.get("/analytics/match/{match_id}/worm", response_model=WormResponse)
async def worm_chart(
    match_id: str,
    db: Session = Depends(get_db),
):
    """Returns cumulative run data per over for worm chart."""
    try:
        data = match_service.get_worm_chart_data(db, match_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Match not found")
        return WormResponse(
            match_id=match_id,
            data=[WormDataPoint(**d) for d in data],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error generating worm data")
        raise HTTPException(status_code=500, detail="Internal server error")


# ═══════════════════════════════════════════════════════════════════
# GET /stats
# ═══════════════════════════════════════════════════════════════════

@router.get("/stats", response_model=StatsResponse)
async def stats(db: Session = Depends(get_db)):
    """Returns database counts."""
    try:
        return StatsResponse(**match_service.get_stats(db))
    except Exception as e:
        logger.exception("Error fetching stats")
        raise HTTPException(status_code=500, detail="Internal server error")


# ═══════════════════════════════════════════════════════════════════
# GET /health
# ═══════════════════════════════════════════════════════════════════

@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check — catches DB connection failure gracefully."""
    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(conn.default_isolation_level if False else
                        __import__("sqlalchemy").text("SELECT 1"))
    except Exception:
        db_status = "error"

    return HealthResponse(status="ok", db=db_status, version=API_VERSION)


# ═══════════════════════════════════════════════════════════════════
# GET /search
# ═══════════════════════════════════════════════════════════════════

@router.get("/search", response_model=GlobalSearchResponse)
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    db: Session = Depends(get_db),
):
    """Global search across players and matches."""
    try:
        results = match_service.global_search(db, q)
        return GlobalSearchResponse(**results)
    except Exception as e:
        logger.exception("Error executing global search")
        raise HTTPException(status_code=500, detail="Internal server error")


# ═══════════════════════════════════════════════════════════════════
# POST /ai/insight  (HuggingFace-powered analyst)
# ═══════════════════════════════════════════════════════════════════

@router.post("/ai/insight", response_model=AIInsightResponse)
async def ai_insight(
    body: AIInsightRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Proxies the HuggingFace Inference API call server-side.
    Implements automatic model fallback on free tier limits.
    """
    if body.context_type not in ("match", "player"):
        raise HTTPException(status_code=422, detail="Invalid context_type")
        
    if not body.context_data:
        raise HTTPException(status_code=422, detail="Context data cannot be empty")

    from service import ai_analyst
    
    # Run sync function in threadpool
    import asyncio
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, 
        ai_analyst.generate_analyst_insight, 
        body.context_data, 
        body.context_type
    )

    logger.info(f"AI Insight generated via {result['model_used']} (attempt {result['attempt']})")
    return AIInsightResponse(**result)


# ═══════════════════════════════════════════════════════════════════
# GET /ml/status
# ═══════════════════════════════════════════════════════════════════

@router.get("/ml/status", response_model=MLStatusResponse)
async def ml_status():
    """Returns the load status and metadata of the xR and xW machine learning models."""
    import os
    from service import enrichment

    metadata_path = os.path.join(os.path.dirname(__file__), "..", "ml", "models", "metadata.json")
    metadata = {}
    
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
        except Exception as e:
            logger.warning(f"Could not read ML metadata: {e}")

    return MLStatusResponse(
        xr_model_loaded=enrichment.xr_model is not None,
        xw_model_loaded=enrichment.xw_model is not None,
        training_date=metadata.get("training_date"),
        sample_size=metadata.get("sample_size"),
    )


# ═══════════════════════════════════════════════════════════════════
# POST /ai/prewarm
# ═══════════════════════════════════════════════════════════════════

@router.post("/ai/prewarm")
async def prewarm_ai_models(background_tasks: BackgroundTasks):
    """
    Triggered by the frontend on load to ping the HuggingFace API.
    This wakes the model from cold sleep (503) so it's hot when the user clicks 'Insight'.
    """
    from service.ai_analyst import prewarm_models
    background_tasks.add_task(prewarm_models)
    return {"status": "prewarming_initiated"}
