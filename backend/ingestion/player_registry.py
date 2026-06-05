"""
Player Registry Module — handles downloading the Cricsheet people registry,
fuzzy matching player names, and resolving identities during ingestion.
"""
import csv
import io
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict

import httpx
from rapidfuzz import process, fuzz
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models import PlayerRegistry, Player, PlayerMergeQueue

logger = logging.getLogger("cricviz.registry")

PEOPLE_CSV_URL = "https://cricsheet.org/register/people.csv"

_CANONICAL_NAMES_CACHE: Dict[str, str] = {}
_LAST_CACHE_REFRESH: float = 0


def download_registry(db: Session) -> int:
    """
    Downloads the official Cricsheet people registry CSV and upserts
    it into the PlayerRegistry table.
    
    Returns:
        int: Number of rows upserted.
    """
    logger.info(f"Downloading player registry from {PEOPLE_CSV_URL}...")
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.get(PEOPLE_CSV_URL, follow_redirects=True)
            resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to download registry: {e}")
        return 0

    csv_text = resp.text
    reader = csv.DictReader(io.StringIO(csv_text))
    
    rows_to_insert = []
    total_upserted = 0
    batch_size = 1000

    dialect = db.get_bind().dialect.name

    for i, row in enumerate(reader, start=1):
        # The CSV has exactly the columns we mapped, except canonical_name which we derive
        db_row = {
            "identifier": row.get("identifier"),
            "name": row.get("name"),
            "unique_name": row.get("unique_name"),
            "canonical_name": row.get("name"),  # using name as canonical_name for searching
            "key_cricinfo": row.get("key_cricinfo"),
            "key_espn": row.get("key_espn"),
            "key_cricbuzz": row.get("key_cricbuzz"),
            "key_bigbash": row.get("key_bigbash"),
            "key_crichq": row.get("key_crichq"),
            "key_opta": row.get("key_opta"),
            "key_nvplay": row.get("key_nvplay"),
            "key_cricsheet": row.get("key_cricsheet"),
            "key_rhino": row.get("key_rhino"),
        }
        rows_to_insert.append(db_row)

        if len(rows_to_insert) >= batch_size:
            _upsert_registry_batch(db, rows_to_insert, dialect)
            total_upserted += len(rows_to_insert)
            rows_to_insert.clear()
            
            if total_upserted % 5000 == 0:
                logger.info(f"Upserted {total_upserted} registry rows so far...")

    if rows_to_insert:
        _upsert_registry_batch(db, rows_to_insert, dialect)
        total_upserted += len(rows_to_insert)

    db.commit()
    logger.info(f"Registry download complete. Total rows upserted: {total_upserted}")
    
    # Invalidate cache
    global _LAST_CACHE_REFRESH
    _LAST_CACHE_REFRESH = 0
    
    return total_upserted


def _upsert_registry_batch(db: Session, rows: list, dialect: str):
    """Helper to perform dialect-specific bulk upserts."""
    if not rows:
        return

    try:
        if dialect == "sqlite":
            stmt = sqlite_insert(PlayerRegistry).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=['identifier'],
                set_={k: stmt.excluded[k] for k in rows[0].keys() if k != 'identifier'}
            )
            db.execute(stmt)
        elif dialect == "postgresql":
            stmt = pg_insert(PlayerRegistry).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=['identifier'],
                set_={k: stmt.excluded[k] for k in rows[0].keys() if k != 'identifier'}
            )
            db.execute(stmt)
        else:
            # Fallback for other DBs
            for row in rows:
                db.merge(PlayerRegistry(**row))
    except Exception as e:
        logger.error(f"Error during registry batch upsert: {e}")
        raise


def _get_registry_cache(db: Session) -> Dict[str, str]:
    """Loads and caches the registry canonical names in memory."""
    global _CANONICAL_NAMES_CACHE, _LAST_CACHE_REFRESH
    now = time.time()
    
    # Refresh cache if empty or older than 24 hours
    if not _CANONICAL_NAMES_CACHE or (now - _LAST_CACHE_REFRESH > 86400):
        logger.info("Refreshing player registry in-memory cache...")
        rows = db.query(PlayerRegistry.canonical_name, PlayerRegistry.identifier).all()
        # In case of exact duplicates, last one wins, which is fine for fuzzy mapping
        _CANONICAL_NAMES_CACHE = {r.canonical_name: r.identifier for r in rows if r.canonical_name}
        _LAST_CACHE_REFRESH = now
        
    return _CANONICAL_NAMES_CACHE


def resolve_player(name: str, identifier: Optional[str], db: Session) -> str:
    """
    Resolves a player name to a canonical Player ID, using identifiers,
    exact matches, and fuzzy matching.

    Args:
        name: The raw player name from the match data.
        identifier: The official cricsheet identifier (if available).
        db: Database session.

    Returns:
        str: The UUID of the resolved/created player in the `players` table.
    """
    if not name:
        return None

    # Step A: Exact Identifier Match
    if identifier:
        registry_entry = db.query(PlayerRegistry).filter(PlayerRegistry.identifier == identifier).first()
        if registry_entry:
            player = db.query(Player).filter(Player.cricsheet_identifier == identifier).first()
            if not player:
                # Check if we already have a player by this name without an identifier to merge
                player = db.query(Player).filter(Player.name == registry_entry.canonical_name).first()
                if player:
                    player.cricsheet_identifier = identifier
                else:
                    player = Player(name=registry_entry.canonical_name, cricsheet_identifier=identifier)
                    db.add(player)
                db.commit()
            return player.id

    # Step B: Exact Canonical Name Match
    registry_entry = db.query(PlayerRegistry).filter(
        func.lower(PlayerRegistry.canonical_name) == name.lower()
    ).first()
    
    if registry_entry:
        player = db.query(Player).filter(Player.cricsheet_identifier == registry_entry.identifier).first()
        if not player:
            player = db.query(Player).filter(Player.name == registry_entry.canonical_name).first()
            if player:
                player.cricsheet_identifier = registry_entry.identifier
            else:
                player = Player(name=registry_entry.canonical_name, cricsheet_identifier=registry_entry.identifier)
                db.add(player)
            db.commit()
        return player.id

    # Step C: Fuzzy Match
    cache = _get_registry_cache(db)
    if cache:
        registry_names = list(cache.keys())
        # extractOne returns (match_string, score, index)
        result = process.extractOne(name, registry_names, scorer=fuzz.WRatio)
        if result:
            best_match, score, _ = result
            
            if score >= 88.0:
                # Auto-merge
                matched_id = cache[best_match]
                player = db.query(Player).filter(Player.cricsheet_identifier == matched_id).first()
                if not player:
                    player = db.query(Player).filter(Player.name == best_match).first()
                    if player:
                        player.cricsheet_identifier = matched_id
                    else:
                        player = Player(name=best_match, cricsheet_identifier=matched_id)
                        db.add(player)
                    db.commit()
                return player.id
                
            elif score >= 70.0:
                # Add to merge queue for manual review, then fall through to create new player
                queue_entry = PlayerMergeQueue(
                    raw_name=name,
                    matched_canonical=best_match,
                    fuzzy_score=float(score),
                    status="pending"
                )
                db.add(queue_entry)
                db.commit()

    # Step D: Create new player
    # See if player with exact raw name already exists (without registry id)
    player = db.query(Player).filter(Player.name == name).first()
    if not player:
        player = Player(name=name)
        db.add(player)
        db.commit()
        
    return player.id


def ensure_registry_fresh(db: Session):
    """
    Startup hook to check if the registry is populated and up-to-date.
    Downloads the registry if it is empty or older than 7 days.
    """
    logger.info("Checking Player Registry freshness...")
    
    count = db.query(func.count(PlayerRegistry.identifier)).scalar()
    needs_update = False
    
    if count == 0:
        logger.info("Player Registry is empty.")
        needs_update = True
    else:
        # Check date of the most recently created/updated entry
        last_entry = db.query(PlayerRegistry).order_by(PlayerRegistry.updated_at.desc()).first()
        if last_entry and last_entry.updated_at:
            if datetime.utcnow() - last_entry.updated_at > timedelta(days=7):
                logger.info("Player Registry is older than 7 days.")
                needs_update = True

    if needs_update:
        try:
            download_registry(db)
        except Exception as e:
            logger.error(f"Failed to refresh Player Registry during startup: {e}")
    else:
        logger.info(f"Player Registry is fresh. Contains {count} players.")
