"""
Pipeline Routes — specialized endpoints for async data pipeline operations.
"""
import uuid
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends

from api.auth import get_current_user
from models import User, APIUsageLog
from ingestion.commentary_enricher import enrich_match, enrich_recent_matches
from database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("cricviz.api.pipeline")

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

class PipelineEnrichRequest(BaseModel):
    match_id: Optional[str] = None
    days_back: int = 7


def _run_enrichment_task(match_id: Optional[str], days_back: int):
    """Background task runner for commentary enrichment."""
    try:
        if match_id:
            logger.info(f"Background task starting: single match enrichment for {match_id}")
            enrich_match(match_id)
        else:
            logger.info(f"Background task starting: recent matches enrichment (last {days_back} days)")
            enrich_recent_matches(days=days_back)
    except Exception as e:
        logger.exception(f"Background enrichment task failed: {e}")


@router.post("/enrich-commentary")
async def pipeline_enrich_commentary(
    body: PipelineEnrichRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Trigger commentary enrichment as a non-blocking background task.
    Requires authentication (admin only).
    """
    task_id = str(uuid.uuid4())
    background_tasks.add_task(_run_enrichment_task, body.match_id, body.days_back)
    
    return {
        "status": "started",
        "task_id": task_id
    }


@router.get("/commentary-usage")
def get_commentary_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get today's CricAPI usage against the 100 hit daily limit."""
    today = datetime.utcnow().date()
    today_used = db.query(APIUsageLog).filter(
        APIUsageLog.api_name == "cricketdata",
        func.date(APIUsageLog.called_at) == today
    ).count()

    last_call = db.query(APIUsageLog.called_at).filter(
        APIUsageLog.api_name == "cricketdata"
    ).order_by(APIUsageLog.called_at.desc()).first()

    now_utc = datetime.utcnow()
    tomorrow_utc = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    return {
        "today_used": today_used,
        "daily_limit": 100,
        "remaining": max(0, 100 - today_used),
        "last_call": last_call[0].isoformat() if last_call else None,
        "reset_at": tomorrow_utc.isoformat()
    }
