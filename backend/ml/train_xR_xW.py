import os
import json
import logging
from datetime import datetime
import sys

# Add backend directory to sys.path so we can import from database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
import joblib

from database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cricviz.ml.train")

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

def load_data() -> pd.DataFrame:
    query = """
    SELECT 
        d.match_id, d.innings, d.over, d.ball,
        d.runs_bat, d.runs_extras, d.wicket_type,
        m.shot_intent, m.pitch_length_zone, m.is_false_shot
    FROM deliveries d
    JOIN cricviz_metrics m ON d.id = m.delivery_id
    ORDER BY d.match_id, d.innings, d.over, d.ball
    """
    df = pd.read_sql(query, engine)
    return df

def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    df["total_runs_on_ball"] = df["runs_bat"] + df["runs_extras"]
    df["is_wicket"] = df["wicket_type"].notnull().astype(int)

    df = df.sort_values(by=["match_id", "innings", "over", "ball"]).reset_index(drop=True)
    
    df["runs_in_over_so_far"] = df.groupby(["match_id", "innings", "over"])["total_runs_on_ball"].cumsum() - df["total_runs_on_ball"]
    df["wickets_in_innings"] = df.groupby(["match_id", "innings"])["is_wicket"].cumsum() - df["is_wicket"]
    
    df["is_false_shot"] = df["is_false_shot"].astype(int)
    
    return df

def train_models():
    df = load_data()
    
    if len(df) < 500:
        logger.error(f"Insufficient data for training. Required: 500, Got: {len(df)}")
        return
        
    logger.info(f"Loaded {len(df)} deliveries for training.")
    df = feature_engineering(df)
    
    features = [
        "shot_intent", "pitch_length_zone", "is_false_shot", 
        "innings", "over", "runs_in_over_so_far", "wickets_in_innings"
    ]
    
    X = df[features]
    y_r = df["runs_bat"]
    y_w = df["is_wicket"]
    
    categorical_features = ["shot_intent", "pitch_length_zone"]
    numerical_features = ["is_false_shot", "innings", "over", "runs_in_over_so_far", "wickets_in_innings"]
    
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
            ("num", "passthrough", numerical_features)
        ]
    )
    
    xr_pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("regressor", GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42))
    ])
    
    xw_pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("regressor", GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42))
    ])
    
    logger.info("Training xR model...")
    xr_pipeline.fit(X, y_r)
    
    logger.info("Training xW model...")
    xw_pipeline.fit(X, y_w)
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    joblib.dump(xr_pipeline, os.path.join(MODELS_DIR, "xR_model.pkl"))
    joblib.dump(xw_pipeline, os.path.join(MODELS_DIR, "xW_model.pkl"))
    
    metadata = {
        "training_date": datetime.utcnow().isoformat(),
        "sample_size": len(df)
    }
    
    with open(os.path.join(MODELS_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f)
        
    logger.info("Models trained and saved successfully.")

if __name__ == "__main__":
    train_models()
