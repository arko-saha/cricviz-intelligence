"""
CSV Bulk Loader — loads consolidated_t20_data.csv into the database.

Groups rows by match_id and delegates to ingestion_service.
Calls Service layer, never Repository directly.
"""
import csv
import logging
from collections import defaultdict
from pathlib import Path

from database import get_db_context
from service import ingestion_service

logger = logging.getLogger("cricviz.csv_loader")


def run_csv_ingestion(csv_path: str, job_id: str = "", max_matches: int = 0):
    """
    Load a Cricsheet-format CSV file into the database.

    Groups by match_id, then calls ingestion_service.ingest_csv_row_batch()
    for each match group in a separate transaction.

    Args:
        csv_path: Path to the CSV file
        job_id: Optional job tracking ID
        max_matches: Max matches to ingest (0 = unlimited)
    """
    if job_id:
        pass # state is managed by the service now

    path = Path(csv_path)
    if not path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return

    try:
        # Group rows by match_id
        match_groups = defaultdict(list)
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mid = row.get("match_id", "")
                if mid:
                    match_groups[mid].append(row)

        logger.info(f"Found {len(match_groups)} matches in CSV")

        count = 0
        for match_id, rows in match_groups.items():
            if max_matches and count >= max_matches:
                break

            source_file = f"csv_{match_id}"
            with get_db_context() as db:
                ingestion_service.ingest_csv_row_batch(
                    db, rows, source_file=source_file, job_id=job_id,
                )
            count += 1

            if count % 50 == 0:
                logger.info(f"Processed {count}/{len(match_groups)} matches")

    except Exception as e:
        logger.exception(f"CSV ingestion error: {e}")
    finally:
        ingestion_service.finalize_job(job_id)
