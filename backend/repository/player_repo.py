"""
Player Repository — all player DB operations.

No business logic here; only read/write through SQLAlchemy ORM.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from rapidfuzz import process, fuzz

from models import Player

logger = logging.getLogger("cricviz.player_repo")

# In-memory cache for fuzzy deduplication to avoid repeated DB scans
_FUZZY_CACHE = {}

def get_fuzzy_player_cache(db: Session, country: str = None) -> list:
    """Returns a list of all player names, optionally filtered by country."""
    cache_key = country or "ALL"
    if cache_key not in _FUZZY_CACHE:
        q = db.query(Player.id, Player.name, Player.country)
        if country:
            q = q.filter(Player.country == country)
        _FUZZY_CACHE[cache_key] = [(r.name, r.id) for r in q.all()]
    return _FUZZY_CACHE[cache_key]

def invalidate_fuzzy_cache():
    """Clear the in-memory fuzzy matching cache."""
    global _FUZZY_CACHE
    _FUZZY_CACHE = {}

def upsert_player(
    db: Session,
    name: str,
    country: Optional[str] = None,
    handedness: Optional[str] = None,
    bowling_style: Optional[str] = None,
) -> Optional[Player]:
    """
    Insert-or-return player by name + country.
    Guards against name collisions from different matches by using
    (name, country) as the lookup key. Uses RapidFuzz for fuzzy deduplication.
    """
    if not name or not name.strip():
        return None
        
    name = name.strip()
    
    # 1. Check exact match
    q = db.query(Player).filter(Player.name == name)
    if country:
        q = q.filter(Player.country == country)
    existing = q.first()
    
    if existing:
        return _update_player_metadata(existing, handedness, bowling_style)

    # 2. Try fuzzy matching against cache
    cache = get_fuzzy_player_cache(db, country)
    if cache:
        names = [item[0] for item in cache]
        best_match = process.extractOne(name, names, scorer=fuzz.token_sort_ratio)
        if best_match and best_match[1] >= 85.0:  # 85% similarity threshold
            matched_name = best_match[0]
            logger.info(f"Fuzzy matched '{name}' -> '{matched_name}' (score: {best_match[1]:.1f})")
            q = db.query(Player).filter(Player.name == matched_name)
            if country:
                q = q.filter(Player.country == country)
            existing = q.first()
            if existing:
                return _update_player_metadata(existing, handedness, bowling_style)

    # 3. Create new player
    player = Player(
        name=name,
        country=country,
        handedness=handedness,
        bowling_style=bowling_style,
    )
    db.add(player)
    db.flush()  # Ensure id is available without committing
    
    # Update cache
    cache_key = country or "ALL"
    if cache_key in _FUZZY_CACHE:
        _FUZZY_CACHE[cache_key].append((name, player.id))
        
    return player

def _update_player_metadata(existing: Player, handedness: Optional[str], bowling_style: Optional[str]) -> Player:
    """Helper to update missing metadata on an existing player."""
    if handedness and not existing.handedness:
        existing.handedness = handedness
    if bowling_style and not existing.bowling_style:
        existing.bowling_style = bowling_style
    return existing

def get_player_by_id(db: Session, player_id: str) -> Optional[Player]:
    return db.query(Player).filter(Player.id == player_id).first()

def get_all_players(db: Session, limit: int = 100, offset: int = 0):
    return db.query(Player).order_by(Player.name).offset(offset).limit(limit).all()

def search_players(db: Session, query: str, limit: int = 5):
    """Search players by name or country using case-insensitive ILIKE."""
    search_term = f"%{query}%"
    return db.query(Player).filter(
        (Player.name.ilike(search_term)) | (Player.country.ilike(search_term))
    ).order_by(Player.name).limit(limit).all()

def count_players(db: Session) -> int:
    return db.query(Player).count()
