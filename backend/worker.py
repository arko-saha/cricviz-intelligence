"""
Celery Worker — task definitions and Beat schedule.

Registers ingestion tasks and the nightly commentary enrichment
job.  Run with::

    celery -A worker worker --beat --loglevel=info
"""
import os

from celery import Celery
from celery.schedules import crontab

from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

# Make sure we don't accidentally get an SQLite threading error since Celery uses multiprocessing.
# Ingestion functions are already wrapping transactions properly.

celery_app = Celery(
    "cricviz_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=4,  # Adjust based on server resources
)


# ═══════════════════════════════════════════════════════════════════
# INGESTION TASKS
# ═══════════════════════════════════════════════════════════════════

# Import and wrap ingestion tasks
from ingestion.parser import run_ingestion as _run_ingestion
from ingestion.csv_loader import run_csv_ingestion as _run_csv_ingestion


@celery_app.task(name="ingestion.run_zip_ingestion", bind=True)
def run_zip_ingestion_task(self, source: str, job_id: str, event_filter: str = None):
    """Celery task for ZIP ingestion"""
    return _run_ingestion(source, job_id, event_filter=event_filter)


@celery_app.task(name="ingestion.run_csv_ingestion", bind=True)
def run_csv_ingestion_task(self, source: str, job_id: str):
    """Celery task for CSV ingestion"""
    return _run_csv_ingestion(source, job_id)


# ═══════════════════════════════════════════════════════════════════
# COMMENTARY ENRICHMENT TASKS
# ═══════════════════════════════════════════════════════════════════

@celery_app.task(name="commentary.enrich_recent", bind=True)
def enrich_recent_commentary_task(self):
    """
    Celery task: enrich recently-ingested matches with commentary.

    Processes matches from the last ``COMMENTARY_ENRICH_DAYS`` days,
    up to ``COMMENTARY_DAILY_LIMIT`` per run.  Scheduled nightly
    via Beat (see below).
    """
    from ingestion.commentary_enricher import enrich_recent_matches

    results = enrich_recent_matches()
    summary = {
        "matches_processed": len(results),
        "deliveries_updated": sum(r.deliveries_updated for r in results),
        "api_hits": sum(1 for r in results if r.api_found),
        "errors": sum(1 for r in results if r.error),
    }
    return summary


@celery_app.task(name="commentary.backfill", bind=True)
def backfill_commentary_task(self):
    """
    Celery task: backfill commentary for all matches with NULL
    commentary.  Intended for one-off manual dispatch::

        from worker import backfill_commentary_task
        backfill_commentary_task.delay()
    """
    from ingestion.commentary_enricher import backfill_all

    results = backfill_all()
    summary = {
        "matches_processed": len(results),
        "deliveries_updated": sum(r.deliveries_updated for r in results),
        "api_hits": sum(1 for r in results if r.api_found),
        "errors": sum(1 for r in results if r.error),
    }
    return summary


@celery_app.task(name="commentary.enrich_match", bind=True)
def enrich_single_match_task(self, match_id: str):
    """
    Celery task: enrich a single match by ID.  Used by the API
    endpoint for manual triggers.
    """
    from ingestion.commentary_enricher import enrich_match

    result = enrich_match(match_id)
    return {
        "match_id": result.match_id,
        "team1": result.team1,
        "team2": result.team2,
        "deliveries_updated": result.deliveries_updated,
        "deliveries_skipped": result.deliveries_skipped,
        "api_found": result.api_found,
        "error": result.error,
    }


# ═══════════════════════════════════════════════════════════════════
# ML RETRAINING TASKS
# ═══════════════════════════════════════════════════════════════════

@celery_app.task(name="ml.retrain", bind=True)
def retrain_ml_models_task(self):
    """
    Celery task: retrain xR / xW LightGBM models and hot-reload.

    Can be triggered manually::

        from worker import retrain_ml_models_task
        retrain_ml_models_task.delay()
    """
    from ml.train import train_models
    from ml import predictor

    result = train_models()
    predictor.reload_models()
    return result


# ═══════════════════════════════════════════════════════════════════
# CELERY BEAT SCHEDULE
# ═══════════════════════════════════════════════════════════════════

@celery_app.task(name="registry.download", bind=True)
def download_registry_task(self):
    from ingestion.player_registry import ensure_registry_fresh
    from database import SessionLocal
    db = SessionLocal()
    try:
        ensure_registry_fresh(db)
    finally:
        db.close()

celery_app.conf.beat_schedule = {
    "download-registry-nightly": {
        "task": "registry.download",
        "schedule": crontab(hour=2, minute=0),
    },
    "retrain-models-weekly": {
        "task": "ml.retrain",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),
    },
}
