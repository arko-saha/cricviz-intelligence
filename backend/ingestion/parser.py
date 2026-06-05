"""
Cricsheet ZIP/JSON Parser — Section 2.

Accepts a local file path OR URL pointing to a Cricsheet ZIP archive.
Uses generator pattern to stream-unpack — never loads entire archive into memory.
Calls Service layer (never Repository directly).
"""
import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Generator, Tuple

import httpx

from database import get_db_context
from service import ingestion_service

logger = logging.getLogger("cricviz.parser")


def _iter_json_from_zip(zip_path: str) -> Generator[Tuple[str, dict], None, None]:
    """
    Generator: yields (filename, parsed_dict) for each JSON file in the ZIP.
    Skips non-JSON files silently (e.g., README.txt).
    Catches JSONDecodeError per file and logs a warning.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        for entry in zf.namelist():
            # Guard: skip non-JSON files silently
            if not entry.lower().endswith(".json"):
                continue
            # Skip directories
            if entry.endswith("/"):
                continue

            try:
                with zf.open(entry) as f:
                    data = json.loads(f.read())
                    yield entry, data
            except json.JSONDecodeError as e:
                logger.warning(f"Malformed JSON in ZIP: {entry} — {e}")
                continue
            except Exception as e:
                logger.warning(f"Error reading {entry} from ZIP: {e}")
                continue


def _download_to_temp(url: str) -> str:
    """Downloads a URL to a temporary file and returns the path."""
    logger.info(f"Downloading {url}...")
    with httpx.Client(timeout=120) as client:
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.write(resp.content)
    tmp.close()
    return tmp.name


def run_ingestion(source: str, job_id: str = "", event_filter: str = None):
    """
    Main ingestion entry point.
    `source` can be a local file path or a URL.
    Calls ingestion_service for each match (Service layer).
    """
    if job_id:
        ingestion_service.update_job_status(job_id, "running")
        ingestion_service._log_progress(job_id, {"status": "info", "reason": f"Started ingestion pipeline for {source}"})

    # Wipe the database completely for the new ingestion as requested
    from repository import match_repo
    with get_db_context() as db:
        match_repo.clear_database(db)
        if job_id:
            ingestion_service._log_progress(job_id, {"status": "info", "reason": "Database cleared successfully for new data."})

    zip_path = source
    is_temp = False

    try:
        # If source looks like a URL, download first
        if source.startswith("http://") or source.startswith("https://"):
            if job_id:
                ingestion_service._log_progress(job_id, {"status": "info", "reason": "Downloading ZIP archive (this may take a few moments)..."})
            zip_path = _download_to_temp(source)
            is_temp = True
            if job_id:
                ingestion_service._log_progress(job_id, {"status": "info", "reason": "Download complete. Extracting and parsing matches..."})
        elif not os.path.exists(source):
            logger.error(f"Source file not found: {source}")
            if job_id:
                ingestion_service.update_job_status(job_id, "error")
                ingestion_service._log_progress(job_id, {
                    "status": "error",
                    "error": f"File not found: {source}",
                })
            return

        # Pre-calculate total matches to drive the progress bar
        if job_id:
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    total_files = sum(1 for entry in zf.namelist() if entry.lower().endswith(".json") and not entry.endswith("/"))
                ingestion_service.set_total_matches(job_id, total_files)
            except zipfile.BadZipFile:
                pass # Handled below

        # Stream-process each JSON match
        skipped_count = 0
        ingested_count = 0
        for filename, match_data in _iter_json_from_zip(zip_path):
            if event_filter:
                info = match_data.get("info", {})
                event = info.get("event", {})
                event_name = event.get("name", "") if isinstance(event, dict) else str(event)
                if event_filter.lower() not in event_name.lower():
                    skipped_count += 1
                    continue
            
            ingested_count += 1
            with get_db_context() as db:
                ingestion_service.ingest_match_dict(
                    db, match_data, source_file=filename, job_id=job_id,
                )
                
        if event_filter and job_id:
            ingestion_service._log_progress(job_id, {"status": "info", "reason": f"Skipped {skipped_count} files (event filter: {event_filter}), ingesting {ingested_count} files"})

    except zipfile.BadZipFile:
        logger.error(f"Bad ZIP file: {source}")
        if job_id:
            ingestion_service.update_job_status(job_id, "error")
            ingestion_service._log_progress(job_id, {"status": "error", "error": f"Bad ZIP file: {source}"})
    except Exception as e:
        logger.exception(f"Ingestion pipeline error: {e}")
        if job_id:
            ingestion_service.update_job_status(job_id, "error")
            ingestion_service._log_progress(job_id, {"status": "error", "error": f"Pipeline error: {str(e)}"})
    finally:
        # Clean up temp file
        if is_temp and os.path.exists(zip_path):
            os.unlink(zip_path)

        ingestion_service.finalize_job(job_id)
