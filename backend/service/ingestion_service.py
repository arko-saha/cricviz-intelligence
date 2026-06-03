"""
Ingestion Service — orchestrates the ingestion pipeline.

Calls the parser/CSV loader, enrichment engine, and repository layer.
Wraps each match in a DB transaction. Logs structured progress.
"""
import logging
import time
import uuid
from typing import Dict, Any

from sqlalchemy.orm import Session

from service.enrichment import enrich_delivery
from repository import match_repo, player_repo

logger = logging.getLogger("cricviz.ingestion")


import json
from models import IngestionJob
from database import SessionLocal

# We no longer use an in-memory _jobs dictionary.
# Instead we persist state to the IngestionJob table.

def create_job() -> str:
    job_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        job = IngestionJob(
            id=job_id,
            status="queued",
            matches_processed=0,
            matches_failed=0,
            total_deliveries=0,
            logs=json.dumps([])
        )
        db.add(job)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to create job {job_id}: {e}")
    finally:
        db.close()
    return job_id


def get_job(job_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            return {"status": "not_found"}
        logs_list = json.loads(job.logs) if job.logs else []
        return {
            "status": job.status,
            "matches_processed": job.matches_processed,
            "matches_failed": job.matches_failed,
            "total_deliveries": job.total_deliveries,
            "total_matches": job.total_matches,
            "logs": logs_list,
        }
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        return {"status": "error"}
    finally:
        db.close()


def set_total_matches(job_id: str, count: int):
    db = SessionLocal()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.total_matches = count
            db.commit()
    except Exception as e:
        logger.error(f"Failed to set total matches for {job_id}: {e}")
    finally:
        db.close()


def update_job_status(job_id: str, status: str):
    db = SessionLocal()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = status
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update job {job_id}: {e}")
    finally:
        db.close()


def _log_progress(job_id: str, entry: Dict[str, Any]):
    logger.info(str(entry))
    if not job_id:
        return
        
    db = SessionLocal()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            logs_list = json.loads(job.logs) if job.logs else []
            logs_list.append(entry)
            job.logs = json.dumps(logs_list)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to log progress for {job_id}: {e}")
    finally:
        db.close()


def _parse_match_metadata(info: dict, source_file: str) -> dict:
    """Extracts match-level metadata from Cricsheet info block."""
    teams = info.get("teams", [])
    team1 = teams[0] if len(teams) > 0 else "Unknown"
    team2 = teams[1] if len(teams) > 1 else "Unknown"

    outcome_data = info.get("outcome", {})
    if not outcome_data:
        outcome_str = "no_result"
    elif "winner" in outcome_data:
        margin = outcome_data.get("by", {})
        margin_str = ""
        if "runs" in margin:
            margin_str = f" by {margin['runs']} runs"
        elif "wickets" in margin:
            margin_str = f" by {margin['wickets']} wickets"
        outcome_str = f"{outcome_data['winner']} won{margin_str}"
    elif "result" in outcome_data:
        outcome_str = outcome_data["result"]
    else:
        outcome_str = "no_result"

    dates = info.get("dates", [])
    
    return {
        "date": dates[0] if dates else "unknown",
        "team1": team1,
        "team2": team2,
        "venue": info.get("venue", "unknown_venue") or "unknown_venue",
        "outcome": outcome_str,
        "match_type": info.get("match_type", "T20"),
        "gender": info.get("gender", "male").lower(),
        "source_file": source_file,
    }


def _process_innings(
    db: Session, 
    match_id: str, 
    innings_list: list, 
    player_cache: dict, 
    source_file: str,
    match_commentary: dict
) -> tuple[int, int]:
    """Processes all innings and deliveries for a match."""
    deliveries_parsed = 0
    deliveries_enriched = 0
    
    def get_or_create_player(name: str, country: str = None) -> Any:
        if not name:
            return None
        cache_key = f"{name}|{country or ''}"
        if cache_key in player_cache:
            return player_cache[cache_key]
        p = player_repo.upsert_player(db, name=name, country=country)
        player_cache[cache_key] = p
        return p

    for inning_idx, inning in enumerate(innings_list, start=1):
        team = inning.get("team", "")
        overs = inning.get("overs", [])

        wickets_in_innings = 0
        for over_data in overs:
            runs_in_over_so_far = 0
            over_num = over_data.get("over", 0)
            deliveries = over_data.get("deliveries", [])

            for ball_idx, del_dict in enumerate(deliveries, start=1):
                batter_name = del_dict.get("batter")
                if not batter_name:
                    logger.warning(
                        f"Delivery missing batter in {source_file} "
                        f"innings={inning_idx} over={over_num} ball={ball_idx}"
                    )
                    continue

                bowler_name = del_dict.get("bowler", "Unknown")

                batter = get_or_create_player(batter_name, team)
                bowler = get_or_create_player(bowler_name)
                
                if not batter or not bowler:
                    continue

                runs_data = del_dict.get("runs", {})
                runs_bat = runs_data.get("batter", 0) if runs_data else 0
                runs_extras = runs_data.get("extras", 0) if runs_data else 0
                if runs_bat is None: runs_bat = 0
                if runs_extras is None: runs_extras = 0

                wicket_type = None
                fielder_id = None
                wickets = del_dict.get("wickets", [])
                if wickets:
                    w = wickets[0]
                    wicket_type = w.get("kind")
                    fielders = w.get("fielders", [])
                    if fielders:
                        f_name = fielders[0].get("name", "")
                        if f_name:
                            fielder = get_or_create_player(f_name)
                            if fielder:
                                fielder_id = fielder.id

                deliveries_parsed += 1

                commentary = del_dict.get("commentary", "")
                if not commentary and match_commentary:
                    commentary = match_commentary.get(f"{inning_idx}_{over_num}_{ball_idx}", "")

                bowler_style = bowler.bowling_style or ""
                metrics = enrich_delivery(
                    del_dict, commentary, bowler_style,
                    innings=inning_idx, over_number=over_num,
                    runs_in_over_so_far=runs_in_over_so_far,
                    wickets_in_innings=wickets_in_innings
                )
                
                runs_in_over_so_far += (runs_bat + runs_extras)
                if wicket_type:
                    wickets_in_innings += 1
                    
                deliveries_enriched += 1

                delivery = match_repo.create_delivery(
                    db,
                    match_id=match_id,
                    innings=inning_idx,
                    over=over_num,
                    ball=ball_idx,
                    batter_id=batter.id,
                    bowler_id=bowler.id,
                    runs_bat=runs_bat,
                    runs_extras=runs_extras,
                    wicket_type=wicket_type,
                    fielder_id=fielder_id,
                )

                match_repo.create_metric(db, delivery_id=delivery.id, **metrics)
                
    return deliveries_parsed, deliveries_enriched


def ingest_match_dict(
    db: Session,
    match_data: dict,
    source_file: str,
    job_id: str = "",
) -> Dict[str, Any]:
    """
    Ingest a single match from a parsed Cricsheet JSON dict.
    Wraps in a transaction — rolls back on error.
    """
    start = time.time()
    deliveries_parsed = 0

    try:
        # Check for duplicate
        if match_repo.get_match_by_source_file(db, source_file):
            entry = {"status": "skipped", "file": source_file, "reason": "duplicate"}
            _log_progress(job_id, entry)
            return entry

        info = match_data.get("info", {})
        innings_list = match_data.get("innings", [])
        
        if not innings_list:
            entry = {"status": "skipped", "file": source_file, "reason": "empty_innings"}
            _log_progress(job_id, entry)
            return entry

        # Create match record
        match_meta = _parse_match_metadata(info, source_file)
        match = match_repo.create_match(db, **match_meta)

        # Pre-populate player cache from registry
        player_cache: Dict[str, Any] = {}
        registry = info.get("registry", {}).get("people", {})
        for player_name in registry:
            if player_name:
                p = player_repo.upsert_player(db, name=player_name)
                player_cache[f"{player_name}|"] = p

        import os
        from service.commentary_client import fetch_match_commentary
        cricsheet_id = os.path.splitext(os.path.basename(source_file))[0]
        match_commentary = fetch_match_commentary(cricsheet_id)

        # Parse innings
        parsed, enriched = _process_innings(db, match.id, innings_list, player_cache, source_file, match_commentary)
        deliveries_parsed = parsed

        db.commit()

        duration_ms = int((time.time() - start) * 1000)
        entry = {
            "status": "ok",
            "file": source_file,
            "deliveries_parsed": parsed,
            "deliveries_enriched": enriched,
            "duration_ms": duration_ms,
        }

        if job_id:
            try:
                job_db = SessionLocal()
                job = job_db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                if job:
                    job.matches_processed += 1
                    job.total_deliveries += parsed
                    job_db.commit()
            except Exception as e:
                logger.error(f"Error updating job state: {e}")
            finally:
                if 'job_db' in locals():
                    job_db.close()

        _log_progress(job_id, entry)
        return entry

    except Exception as e:
        db.rollback()
        duration_ms = int((time.time() - start) * 1000)
        entry = {
            "status": "error",
            "file": source_file,
            "error": str(e),
            "deliveries_parsed": deliveries_parsed,
            "duration_ms": duration_ms,
        }

        if job_id:
            try:
                job_db = SessionLocal()
                job = job_db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                if job:
                    job.matches_failed += 1
                    job_db.commit()
            except Exception as e:
                logger.error(f"Error updating job state: {e}")
            finally:
                if 'job_db' in locals():
                    job_db.close()

        _log_progress(job_id, entry)
        logger.exception(f"Failed to ingest {source_file}")
        return entry


def ingest_csv_row_batch(
    db: Session,
    rows: list,
    source_file: str,
    job_id: str = "",
) -> Dict[str, Any]:
    """
    Ingest a batch of CSV rows (grouped by match_id) into the database.
    Each batch = one match. Wraps in a single DB transaction.
    """
    start = time.time()
    deliveries_parsed = 0
    deliveries_enriched = 0

    try:
        if not rows:
            return {"status": "skipped", "file": source_file, "reason": "empty"}

        if match_repo.get_match_by_source_file(db, source_file):
            return {"status": "skipped", "file": source_file, "reason": "duplicate"}

        first = rows[0]
        venue = first.get("venue", "unknown_venue") or "unknown_venue"

        teams = set()
        for r in rows:
            teams.add(r.get("batting_team", ""))
            teams.add(r.get("bowling_team", ""))
        teams.discard("")
        team_list = sorted(teams)
        team1 = team_list[0] if len(team_list) > 0 else "Unknown"
        team2 = team_list[1] if len(team_list) > 1 else "Unknown"

        match = match_repo.create_match(
            db,
            date=first.get("start_date", "unknown"),
            team1=team1,
            team2=team2,
            venue=venue,
            outcome="see_data",
            match_type=first.get("match_type", "T20"),
            gender=first.get("gender", "male").lower(),
            source_file=source_file,
        )

        player_cache: Dict[str, Any] = {}

        def get_player(name: str) -> Any:
            if not name:
                return None
            if name in player_cache:
                return player_cache[name]
            p = player_repo.upsert_player(db, name=name)
            player_cache[name] = p
            return p

        current_innings = None
        current_over = None
        runs_in_over_so_far = 0
        wickets_in_innings = 0

        for row in rows:
            batter_name = row.get("batter", "")
            if not batter_name:
                continue

            bowler_name = row.get("bowler", "Unknown")
            batter = get_player(batter_name)
            bowler = get_player(bowler_name)
            
            if not batter or not bowler:
                continue

            runs_bat = int(row.get("runs_off_bat", 0) or 0)
            extras = int(row.get("extras", 0) or 0)
            innings = int(row.get("innings", 1) or 1)
            over = int(row.get("over", 0) or 0)
            ball = int(row.get("ball", 1) or 1)
            wicket_type = row.get("wicket_type") or None
            if wicket_type == "":
                wicket_type = None

            if innings != current_innings:
                current_innings = innings
                wickets_in_innings = 0
            if over != current_over:
                current_over = over
                runs_in_over_so_far = 0

            deliveries_parsed += 1

            del_dict = {
                "runs_bat": runs_bat,
                "runs": {"batter": runs_bat, "extras": extras, "total": runs_bat + extras},
                "wicket_type": wicket_type,
            }

            metrics = enrich_delivery(
                del_dict, commentary="", bowler_style="",
                innings=innings, over_number=over,
                runs_in_over_so_far=runs_in_over_so_far,
                wickets_in_innings=wickets_in_innings
            )
            
            runs_in_over_so_far += (runs_bat + extras)
            if wicket_type:
                wickets_in_innings += 1
                
            deliveries_enriched += 1

            delivery = match_repo.create_delivery(
                db,
                match_id=match.id,
                innings=innings,
                over=over,
                ball=ball,
                batter_id=batter.id,
                bowler_id=bowler.id,
                runs_bat=runs_bat,
                runs_extras=extras,
                wicket_type=wicket_type,
            )

            match_repo.create_metric(db, delivery_id=delivery.id, **metrics)

        db.commit()
        duration_ms = int((time.time() - start) * 1000)

        if job_id:
            try:
                job_db = SessionLocal()
                job = job_db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                if job:
                    job.matches_processed += 1
                    job.total_deliveries += deliveries_parsed
                    job_db.commit()
            except Exception as e:
                logger.error(f"Error updating job state: {e}")
            finally:
                if 'job_db' in locals():
                    job_db.close()

        return {
            "status": "ok",
            "file": source_file,
            "deliveries_parsed": deliveries_parsed,
            "deliveries_enriched": deliveries_enriched,
            "duration_ms": duration_ms,
        }

    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to ingest CSV batch {source_file}")
        return {"status": "error", "file": source_file, "error": str(e)}


def finalize_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = "completed"
            db.commit()
    except Exception as e:
        logger.error(f"Failed to finalize job {job_id}: {e}")
    finally:
        db.close()
