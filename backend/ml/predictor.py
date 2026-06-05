import os
import joblib
import pandas as pd
import logging
from typing import Dict, Any, Optional
from models import Delivery, Match, CricvizMetric

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
XR_MODEL_PATH = os.path.join(MODELS_DIR, "xR_lgb.pkl")
XW_MODEL_PATH = os.path.join(MODELS_DIR, "xW_lgb_calibrated.pkl")
VENUE_ENCODER_PATH = os.path.join(MODELS_DIR, "..", "encoders", "venue_encoder.pkl")

class CricVizPredictor:
    def __init__(self):
        self.xr_model = None
        self.xw_model = None
        self.venue_encoder = None
        self.models_available = False
        
        try:
            if os.path.exists(XR_MODEL_PATH) and os.path.exists(XW_MODEL_PATH):
                self.xr_model = joblib.load(XR_MODEL_PATH)
                self.xw_model = joblib.load(XW_MODEL_PATH)
                self.models_available = True
                logger.info("Successfully loaded xR and xW ML models.")
            else:
                logger.info("ML models not found. Predictor will return -1.0")
                
            if os.path.exists(VENUE_ENCODER_PATH):
                self.venue_encoder = joblib.load(VENUE_ENCODER_PATH)
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            self.models_available = False

    def reload(self):
        """Reload models from disk after retraining."""
        logger.info("Hot-reloading ML models...")
        try:
            if os.path.exists(XR_MODEL_PATH) and os.path.exists(XW_MODEL_PATH):
                self.xr_model = joblib.load(XR_MODEL_PATH)
                self.xw_model = joblib.load(XW_MODEL_PATH)
                self.models_available = True
                logger.info("Successfully reloaded xR and xW ML models.")
            else:
                logger.warning("ML models not found during reload.")
                self.models_available = False
                
            if os.path.exists(VENUE_ENCODER_PATH):
                self.venue_encoder = joblib.load(VENUE_ENCODER_PATH)
        except Exception as e:
            logger.error(f"Error reloading models: {e}")
            self.models_available = False

    def delivery_to_features(self, delivery: Delivery, match: Match, metrics: CricvizMetric) -> Dict[str, Any]:
        """
        Extract the same feature dict as training, handling nulls identically.
        """
        # Phase derivation
        over = delivery.over + (delivery.ball - 1) / 10.0
        if over < 6:
            phase = 0
        elif over < 15:
            phase = 1
        else:
            phase = 2

        # Pace derivation
        pace_styles = ['RF', 'RFM', 'LF', 'LFM', 'MF', 'RMF', 'LMF']
        bowling_style = delivery.bowler.bowling_style if delivery.bowler else None
        is_pace = 1 if bowling_style in pace_styles else 0

        # Venue encoding
        venue_str = match.venue if match.venue else "unknown"
        if self.venue_encoder:
            try:
                venue_idx = self.venue_encoder.transform([venue_str])[0]
            except ValueError:
                venue_idx = 0
        else:
            venue_idx = 0

        # Intent mapping
        intent_map = {"UNKNOWN": 0, "DEFENSIVE": 1, "ATTACKING": 2, "MISTIMED": 3}
        shot_intent_str = metrics.shot_intent if metrics and metrics.shot_intent else "UNKNOWN"
        shot_intent = intent_map.get(shot_intent_str.upper(), 0)

        # Zone mapping
        zone_map = {"UNKNOWN": 0, "FULL": 1, "GOOD_LENGTH": 2, "SHORT": 3}
        pitch_zone_str = metrics.pitch_length_zone if metrics and metrics.pitch_length_zone else "UNKNOWN"
        pitch_zone = zone_map.get(pitch_zone_str.upper(), 0)

        # False shot
        computed_false_shot = 1 if metrics and metrics.is_false_shot else 0

        # For prediction, we need to know batting position. 
        # For real-time inference, this would ideally be tracked in state or passed.
        # Fallback to median 6 if not available in this simplified extraction.
        batting_position = 6

        features = {
            "batting_position": batting_position,
            "phase": phase,
            "ball_number": delivery.ball,
            "is_pace": is_pace,
            "venue": venue_idx,
            "shot_intent": shot_intent,
            "pitch_zone": pitch_zone,
            "computed_false_shot": computed_false_shot
        }
        return features

    def predict_xR(self, delivery_features: Dict[str, Any]) -> float:
        if not self.models_available:
            return -1.0
            
        try:
            df = pd.DataFrame([delivery_features])
            pred = float(self.xr_model.predict(df)[0])
            return round(max(0.0, min(pred, 6.0)), 4)
        except Exception as e:
            logger.error(f"xR prediction error: {e}")
            return -1.0

    def predict_xW(self, delivery_features: Dict[str, Any]) -> float:
        if not self.models_available:
            return -1.0
            
        try:
            df = pd.DataFrame([delivery_features])
            if hasattr(self.xw_model, "predict_proba"):
                pred = float(self.xw_model.predict_proba(df)[0, 1])
            else:
                pred = float(self.xw_model.predict(df)[0])
            return round(max(0.0, min(pred, 1.0)), 4)
        except Exception as e:
            logger.error(f"xW prediction error: {e}")
            return -1.0
