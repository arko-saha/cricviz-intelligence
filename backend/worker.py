import os
from celery import Celery

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

# Import and wrap ingestion tasks
from ingestion.parser import run_ingestion as _run_ingestion
from ingestion.csv_loader import run_csv_ingestion as _run_csv_ingestion

@celery_app.task(name="ingestion.run_zip_ingestion", bind=True)
def run_zip_ingestion_task(self, source: str, job_id: str):
    """Celery task for ZIP ingestion"""
    return _run_ingestion(source, job_id)

@celery_app.task(name="ingestion.run_csv_ingestion", bind=True)
def run_csv_ingestion_task(self, source: str, job_id: str):
    """Celery task for CSV ingestion"""
    return _run_csv_ingestion(source, job_id)
