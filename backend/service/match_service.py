"""
Match Service — business logic for match/delivery/player operations.

Delegates DB operations to Repository layer.
Never calls FastAPI objects directly.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from repository import match_repo, player_repo


def get_matches(
    db: Session, 
    page: int = 1, 
    limit: int = 20,
    team: Optional[str] = None,
    venue: Optional[str] = None,
    year: Optional[str] = None,
    gender: Optional[str] = None,
) -> Dict[str, Any]:
    matches, total = match_repo.get_matches_paginated(db, page, limit, team, venue, year, gender)
    return {
        "matches": [
            {
                "id": m.id,
                "date": m.date,
                "team1": m.team1,
                "team2": m.team2,
                "venue": m.venue,
                "outcome": m.outcome,
                "match_type": m.match_type,
                "gender": m.gender,
            }
            for m in matches
        ],
        "total": total,
        "page": max(1, page),
        "limit": limit,
    }


def get_match_deliveries(
    db: Session,
    match_id: str,
    innings: Optional[int] = None,
    over: Optional[int] = None,
) -> Optional[List[Dict[str, Any]]]:
    match = match_repo.get_match_by_id(db, match_id)
    if not match:
        return None
    return match_repo.get_deliveries_for_match(db, match_id, innings, over)


def get_worm_chart_data(db: Session, match_id: str) -> Optional[Dict[str, Any]]:
    match = match_repo.get_match_by_id(db, match_id)
    if not match:
        return None
    data = match_repo.get_worm_data(db, match_id)
    return {
        "match_id": match_id,
        "team1": match.team1,
        "team2": match.team2,
        "data": data
    }


def get_player_profile(db: Session, player_id: str) -> Optional[Dict[str, Any]]:
    return match_repo.get_player_aggregated_metrics(db, player_id)


def get_stats(db: Session) -> Dict[str, int]:
    return {
        "matches": match_repo.count_matches(db),
        "players": player_repo.count_players(db),
        "deliveries": match_repo.count_deliveries(db),
        "enriched_metrics": match_repo.count_metrics(db),
    }


def global_search(db: Session, query: str) -> Dict[str, Any]:
    """Search for matches and players matching the query."""
    players = player_repo.search_players(db, query, limit=5)
    matches = match_repo.search_matches(db, query, limit=5)
    
    return {
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "country": p.country,
            }
            for p in players
        ],
        "matches": [
            {
                "id": m.id,
                "team1": m.team1,
                "team2": m.team2,
                "date": m.date,
                "venue": m.venue,
            }
            for m in matches
        ],
    }
