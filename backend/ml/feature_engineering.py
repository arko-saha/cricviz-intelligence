"""
Feature Engineering Module for ML.
Builds training datasets from the database for xR and xW modeling.
"""
import os
import logging
from typing import Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session
from sklearn.preprocessing import LabelEncoder
import joblib

logger = logging.getLogger(__name__)

def build_feature_dataframe(db: Session, min_matches: int = 500) -> pd.DataFrame:
    """
    Builds a DataFrame where each row is one delivery with derived features.
    
    Args:
        db: SQLAlchemy database session.
        min_matches: Minimum number of matches required to proceed.
        
    Returns:
        pd.DataFrame containing features and targets.
    """
    # Verify match count
    match_count_res = db.execute(text("SELECT COUNT(id) FROM matches")).scalar()
    if match_count_res < min_matches:
        logger.warning(f"Insufficient matches. Have {match_count_res}, need {min_matches}.")
    
    # Query the deliveries, joining with matches, players (for bowler), and metrics.
    # Note: batting_position requires a complex window function or rank.
    # We will compute batting_position using a subquery grouping by innings and ordering by delivery time.
    
    query = """
    WITH BatterOrder AS (
        SELECT 
            match_id, 
            innings, 
            batter_id,
            MIN("over" * 10 + ball) as first_faced
        FROM deliveries
        GROUP BY match_id, innings, batter_id
    ),
    BatterPos AS (
        SELECT 
            match_id, 
            innings, 
            batter_id,
            ROW_NUMBER() OVER(PARTITION BY match_id, innings ORDER BY first_faced) as batting_position
        FROM BatterOrder
    )
    SELECT 
        d.id as delivery_id,
        d.runs_bat as runs_off_bat,
        d.runs_extras as extras,
        (d.runs_bat + d.runs_extras) as total_runs,
        CASE WHEN d.wicket_type IS NOT NULL AND d.wicket_type != '' THEN 1 ELSE 0 END as is_wicket,
        (d."over" + (d.ball - 1) / 10.0) as over_number,
        d."over",
        d.ball as ball_number,
        bp.batting_position,
        p_bowler.bowling_style,
        m.venue,
        m.match_type as match_format,
        m.date as match_date,
        cm.shot_intent,
        cm.pitch_length_zone as pitch_zone,
        cm.is_false_shot as computed_false_shot
    FROM deliveries d
    JOIN matches m ON d.match_id = m.id
    LEFT JOIN BatterPos bp ON d.match_id = bp.match_id AND d.innings = bp.innings AND d.batter_id = bp.batter_id
    LEFT JOIN players p_bowler ON d.bowler_id = p_bowler.id
    LEFT JOIN cricviz_metrics cm ON d.id = cm.delivery_id
    """
    
    logger.info("Executing feature engineering query...")
    df = pd.read_sql(query, db.get_bind())
    
    # Derived features
    def get_phase(over: int) -> str:
        if over < 6:
            return "powerplay"
        elif over < 15:
            return "middle"
        else:
            return "death"
            
    df['phase'] = df['over'].apply(get_phase)
    
    pace_styles = ['RF', 'RFM', 'LF', 'LFM', 'MF', 'RMF', 'LMF']
    df['is_pace'] = df['bowling_style'].apply(
        lambda x: True if pd.notna(x) and x in pace_styles else False
    )
    
    # Match format
    df['match_format'] = df['match_format'].apply(lambda x: "t20" if str(x).upper() in ["T20", "T20I"] else str(x).lower())
    
    # Target columns
    df['target_xR'] = df['runs_off_bat'].astype(int)
    df['target_xW'] = df['is_wicket'].astype(int)
    
    # ENCODING
    # Phase
    phase_map = {"powerplay": 0, "middle": 1, "death": 2}
    df['phase'] = df['phase'].map(phase_map)
    
    # Venue
    encoder_dir = os.path.join(os.path.dirname(__file__), "encoders")
    os.makedirs(encoder_dir, exist_ok=True)
    encoder_path = os.path.join(encoder_dir, "venue_encoder.pkl")
    
    le = LabelEncoder()
    df['venue'] = df['venue'].fillna('unknown')
    df['venue'] = le.fit_transform(df['venue'])
    joblib.dump(le, encoder_path)
    
    # Shot intent
    intent_map = {"UNKNOWN": 0, "DEFENSIVE": 1, "ATTACKING": 2, "MISTIMED": 3}
    df['shot_intent'] = df['shot_intent'].fillna("UNKNOWN").str.upper().map(intent_map).fillna(0).astype(int)
    
    # Pitch zone
    zone_map = {"UNKNOWN": 0, "FULL": 1, "GOOD_LENGTH": 2, "SHORT": 3}
    df['pitch_zone'] = df['pitch_zone'].fillna("UNKNOWN").str.upper().map(zone_map).fillna(0).astype(int)
    
    # Batting position
    df['batting_position'] = df['batting_position'].fillna(6).astype(int)
    
    # is_pace
    df['is_pace'] = df['is_pace'].fillna(False).astype(int)
    
    # false shot
    df['computed_false_shot'] = df['computed_false_shot'].fillna(False).astype(int)
    
    # Set index
    df.set_index('delivery_id', inplace=True)
    
    # Drop intermediate columns
    df.drop(columns=['over', 'bowling_style'], inplace=True, errors='ignore')
    
    return df


def train_test_split_by_year(df: pd.DataFrame, test_year: int = 2024) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits the dataframe into training and testing sets based on match year.
    
    Args:
        df: The feature dataframe (must contain match_date).
        test_year: The year to split on.
        
    Returns:
        (train_df, test_df)
    """
    from sklearn.model_selection import train_test_split
    
    # Extract year from YYYY-MM-DD
    year_col = pd.to_datetime(df['match_date']).dt.year
    
    train_df = df[year_col < test_year].copy()
    test_df = df[year_col >= test_year].copy()
    
    if train_df.empty or test_df.empty:
        logger.warning(f"Year split resulted in empty train/test set. Falling back to random 80/20 split.")
        train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    
    return train_df, test_df
