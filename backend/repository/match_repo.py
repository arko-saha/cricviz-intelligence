"""
Match / Delivery / Metrics Repository — all DB read/write operations.

Aggregations are computed here via SQLAlchemy expressions so the Service
layer never iterates raw Python loops over large result sets.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case

from models import Match, Delivery, CricvizMetric, Player


# ═══════════════════════════════════════════════════════════════════
# MATCH CRUD
# ═══════════════════════════════════════════════════════════════════

def clear_database(db: Session):
    """Wipes all prior data before starting a new ingestion pipeline."""
    db.query(CricvizMetric).delete()
    db.query(Delivery).delete()
    db.query(Match).delete()
    db.query(Player).delete()
    db.commit()

def create_match(db: Session, **kwargs) -> Match:
    m = Match(**kwargs)
    db.add(m)
    db.flush()
    return m


def get_match_by_source_file(db: Session, source_file: str) -> Optional[Match]:
    return db.query(Match).filter(Match.source_file == source_file).first()


def get_match_by_id(db: Session, match_id: str) -> Optional[Match]:
    return db.query(Match).filter(Match.id == match_id).first()


def get_matches_paginated(
    db: Session, 
    page: int = 1, 
    limit: int = 20,
    team: Optional[str] = None,
    venue: Optional[str] = None,
    year: Optional[str] = None,
    gender: Optional[str] = None,
) -> tuple[List[Match], int]:
    """Returns (matches, total_count) with pagination guards and optional filters."""
    # Guard against page <= 0 or negative values
    page = max(1, page)
    limit = max(1, min(limit, 100))

    q = db.query(Match)
    
    if team:
        search_team = f"%{team}%"
        q = q.filter((Match.team1.ilike(search_team)) | (Match.team2.ilike(search_team)))
    if venue:
        q = q.filter(Match.venue.ilike(f"%{venue}%"))
    if year:
        q = q.filter(Match.date.startswith(year))
    if gender:
        q = q.filter(Match.gender.ilike(gender))

    total = q.count()
    offset = (page - 1) * limit
    matches = (
        q.order_by(Match.date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return matches, total


def count_matches(db: Session) -> int:
    return db.query(Match).count()

def search_matches(db: Session, query: str, limit: int = 5):
    """Search matches by team or venue using case-insensitive ILIKE."""
    search_term = f"%{query}%"
    return db.query(Match).filter(
        (Match.team1.ilike(search_term)) | 
        (Match.team2.ilike(search_term)) | 
        (Match.venue.ilike(search_term))
    ).order_by(Match.date.desc()).limit(limit).all()


# ═══════════════════════════════════════════════════════════════════
# DELIVERY CRUD
# ═══════════════════════════════════════════════════════════════════

def create_delivery(db: Session, **kwargs) -> Delivery:
    d = Delivery(**kwargs)
    db.add(d)
    db.flush()
    return d


def create_metric(db: Session, **kwargs) -> CricvizMetric:
    m = CricvizMetric(**kwargs)
    db.add(m)
    db.flush()
    return m


def get_deliveries_for_match(
    db: Session,
    match_id: str,
    innings: Optional[int] = None,
    over: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Returns deliveries with joined player names and cricviz metrics.
    """
    batter = db.query(Player).subquery("batter_sq")
    bowler = db.query(Player).subquery("bowler_sq")

    q = (
        db.query(
            Delivery.id,
            Delivery.innings,
            Delivery.over,
            Delivery.ball,
            Delivery.runs_bat,
            Delivery.runs_extras,
            Delivery.wicket_type,
            Player.name.label("batter_name"),
            CricvizMetric.shot_intent,
            CricvizMetric.pitch_length_zone,
            CricvizMetric.is_false_shot,
            CricvizMetric.computed_xR,
            CricvizMetric.computed_xW,
        )
        .join(CricvizMetric, CricvizMetric.delivery_id == Delivery.id, isouter=True)
        .join(Player, Player.id == Delivery.batter_id)
        .filter(Delivery.match_id == match_id)
    )

    if innings is not None:
        q = q.filter(Delivery.innings == innings)
    if over is not None:
        q = q.filter(Delivery.over == over)

    q = q.order_by(Delivery.innings, Delivery.over, Delivery.ball)
    rows = q.all()

    # We also need bowler name — do a second pass with join
    bowler_names = {
        d.id: d.bowler.name
        for d in (
            db.query(Delivery)
            .options(joinedload(Delivery.bowler))
            .filter(Delivery.match_id == match_id)
            .all()
        )
    }

    return [
        {
            "id": r.id,
            "innings": r.innings,
            "over": r.over,
            "ball": r.ball,
            "batter": r.batter_name,
            "bowler": bowler_names.get(r.id, ""),
            "runs_bat": r.runs_bat,
            "runs_extras": r.runs_extras,
            "wicket_type": r.wicket_type,
            "shot_intent": r.shot_intent or "UNKNOWN",
            "pitch_zone": r.pitch_length_zone or "UNKNOWN",
            "is_false_shot": r.is_false_shot or False,
            "xR": r.computed_xR or 0.0,
            "xW": r.computed_xW or 0.0,
        }
        for r in rows
    ]


def count_deliveries(db: Session) -> int:
    return db.query(Delivery).count()


def count_metrics(db: Session) -> int:
    return db.query(CricvizMetric).count()


# ═══════════════════════════════════════════════════════════════════
# WORM CHART DATA
# ═══════════════════════════════════════════════════════════════════

def get_worm_data(db: Session, match_id: str) -> List[Dict[str, Any]]:
    """
    Returns cumulative run data per over for both innings.
    Format: [{ over, innings1_runs, innings2_runs }]
    """
    # Get total runs per over per innings
    rows = (
        db.query(
            Delivery.innings,
            Delivery.over,
            func.sum(Delivery.runs_bat + Delivery.runs_extras).label("total_runs"),
        )
        .filter(Delivery.match_id == match_id)
        .group_by(Delivery.innings, Delivery.over)
        .order_by(Delivery.innings, Delivery.over)
        .all()
    )

    # Build per-innings data
    innings_data: Dict[int, Dict[int, int]] = {}
    for r in rows:
        innings_data.setdefault(r.innings, {})[r.over] = r.total_runs

    # Find max overs across all innings
    all_overs = set()
    for overs in innings_data.values():
        all_overs.update(overs.keys())

    if not all_overs:
        return []

    max_over = max(all_overs)

    # Build cumulative worm
    result = []
    cum1, cum2 = 0, 0
    for ov in range(0, max_over + 1):
        cum1 += innings_data.get(1, {}).get(ov, 0)
        cum2 += innings_data.get(2, {}).get(ov, 0)
        result.append({
            "over": ov + 1,  # 1-indexed for display
            "innings1_runs": cum1,
            "innings2_runs": cum2,
        })

    return result


# ═══════════════════════════════════════════════════════════════════
# PLAYER AGGREGATIONS (computed in DB, not Python loops)
# ═══════════════════════════════════════════════════════════════════

def get_player_aggregated_metrics(
    db: Session, player_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Returns aggregated CricViz metrics for a player as batter.
    All computed via SQLAlchemy expressions — no Python loops.
    """
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        return None

    # Batting metrics
    batting = (
        db.query(
            func.count(Delivery.id).label("total_deliveries"),
            func.avg(CricvizMetric.computed_xR).label("avg_xR"),
            func.avg(CricvizMetric.computed_xW).label("avg_xW"),
            func.avg(
                case(
                    (CricvizMetric.is_false_shot == True, 1.0),  # noqa: E712
                    else_=0.0,
                )
            ).label("false_shot_pct"),
        )
        .join(CricvizMetric, CricvizMetric.delivery_id == Delivery.id, isouter=True)
        .filter(Delivery.batter_id == player_id)
        .first()
    )

    # Dominant shot intent
    dominant_intent_row = (
        db.query(
            CricvizMetric.shot_intent,
            func.count(CricvizMetric.delivery_id).label("cnt"),
        )
        .join(Delivery, Delivery.id == CricvizMetric.delivery_id)
        .filter(Delivery.batter_id == player_id)
        .filter(CricvizMetric.shot_intent != "UNKNOWN")
        .group_by(CricvizMetric.shot_intent)
        .order_by(func.count(CricvizMetric.delivery_id).desc())
        .first()
    )

    # Dominant pitch zone faced
    dominant_zone_row = (
        db.query(
            CricvizMetric.pitch_length_zone,
            func.count(CricvizMetric.delivery_id).label("cnt"),
        )
        .join(Delivery, Delivery.id == CricvizMetric.delivery_id)
        .filter(Delivery.batter_id == player_id)
        .filter(CricvizMetric.pitch_length_zone != "UNKNOWN")
        .group_by(CricvizMetric.pitch_length_zone)
        .order_by(func.count(CricvizMetric.delivery_id).desc())
        .first()
    )

    # Shot intent distribution
    intent_dist = (
        db.query(
            CricvizMetric.shot_intent,
            func.count(CricvizMetric.delivery_id).label("count"),
        )
        .join(Delivery, Delivery.id == CricvizMetric.delivery_id)
        .filter(Delivery.batter_id == player_id)
        .group_by(CricvizMetric.shot_intent)
        .all()
    )

    # Pitch zone distribution
    zone_dist = (
        db.query(
            CricvizMetric.pitch_length_zone,
            func.count(CricvizMetric.delivery_id).label("count"),
        )
        .join(Delivery, Delivery.id == CricvizMetric.delivery_id)
        .filter(Delivery.batter_id == player_id)
        .group_by(CricvizMetric.pitch_length_zone)
        .all()
    )

    return {
        "player": {
            "id": player.id,
            "name": player.name,
            "handedness": player.handedness,
            "bowling_style": player.bowling_style,
            "country": player.country,
        },
        "total_deliveries_faced": batting.total_deliveries if batting else 0,
        "avg_xR": round(float(batting.avg_xR or 0), 4),
        "avg_xW": round(float(batting.avg_xW or 0), 4),
        "false_shot_pct": round(float(batting.false_shot_pct or 0) * 100, 2),
        "dominant_shot_intent": (
            dominant_intent_row.shot_intent if dominant_intent_row else "UNKNOWN"
        ),
        "dominant_pitch_zone": (
            dominant_zone_row.pitch_length_zone if dominant_zone_row else "UNKNOWN"
        ),
        "shot_intent_distribution": [
            {"intent": r.shot_intent, "count": r.count} for r in intent_dist
        ],
        "pitch_zone_distribution": [
            {"zone": r.pitch_length_zone, "count": r.count} for r in zone_dist
        ],
    }
