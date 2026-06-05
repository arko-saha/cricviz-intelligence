"""
LightGBM Training — xR (regression) and xW (calibrated classification).

Replaces the old sklearn GradientBoostingRegressor pipeline.
Produces two model artifacts:
  - ml/models/xR_lgb.pkl       (LightGBM regressor)
  - ml/models/xW_lgb_calibrated.pkl  (CalibratedClassifierCV wrapping LightGBM)

Also saves backward-compatible filenames (xR_model.pkl, xW_model.pkl) so
the existing enrichment.py model-loading code works without changes.

Usage::

    cd backend
    python -m ml.train
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    brier_score_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)

import lightgbm as lgb

# ── Ensure backend is importable when run as `python -m ml.train` ──
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from database import SessionLocal
from ml.feature_engineering import (
    build_feature_dataframe,
    train_test_split_by_year,
)

FEATURE_COLUMNS = [
    "over_number",
    "ball_number",
    "batting_position",
    "venue",
    "shot_intent",
    "pitch_zone",
    "computed_false_shot",
    "phase",
    "is_pace"
]
CATEGORICAL_FEATURES = ["phase", "venue", "shot_intent", "pitch_zone"]
TARGET_XR = "target_xR"
TARGET_XW = "target_xW"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("cricviz.ml.train")

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")


# ═══════════════════════════════════════════════════════════════════
# HYPERPARAMETERS
# ═══════════════════════════════════════════════════════════════════

XR_PARAMS: Dict[str, Any] = {
    "objective": "regression",
    "metric": "mae",
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "min_child_samples": 50,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "verbose": -1,
}

XW_PARAMS: Dict[str, Any] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "is_unbalance": True,
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "min_child_samples": 50,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "verbose": -1,
}


# ═══════════════════════════════════════════════════════════════════
# TRAINING HELPERS
# ═══════════════════════════════════════════════════════════════════

def _prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Select and prepare feature columns, converting categoricals."""
    X = df[FEATURE_COLUMNS].copy()
    for col in CATEGORICAL_FEATURES:
        X[col] = X[col].astype("category")
    return X


def _train_xr(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> tuple[Any, Dict[str, float]]:
    """Train LightGBM regressor for expected runs."""
    logger.info("Training xR model (LightGBM Regressor)...")
    start = time.time()

    model = lgb.LGBMRegressor(**XR_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.log_evaluation(period=100)],
    )

    duration = time.time() - start
    logger.info("xR training complete in %.1fs.", duration)

    # ── Evaluate ─────────────────────────────────────────────────
    y_pred = model.predict(X_test)
    y_pred = np.clip(y_pred, 0.0, 6.0)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    metrics = {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "training_seconds": round(duration, 1),
    }
    logger.info("xR evaluation — MAE: %.4f, RMSE: %.4f", mae, rmse)
    return model, metrics


def _train_xw(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> tuple[Any, Dict[str, float]]:
    """
    Train LightGBM classifier for expected wickets, then wrap
    in CalibratedClassifierCV for Platt-scaled probabilities.
    """
    logger.info("Training xW model (LightGBM Classifier)...")
    start = time.time()

    base_model = lgb.LGBMClassifier(**XW_PARAMS)
    base_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.log_evaluation(period=100)],
    )

    # ── Platt scaling (isotonic/sigmoid calibration) ──────────────
    logger.info("Calibrating xW probabilities (Platt scaling, cv=5)...")
    calibrated = CalibratedClassifierCV(
        base_model, method="sigmoid", cv=5,
    )
    calibrated.fit(X_train, y_train)

    duration = time.time() - start
    logger.info("xW training + calibration complete in %.1fs.", duration)

    # ── Evaluate ─────────────────────────────────────────────────
    y_prob = calibrated.predict_proba(X_test)[:, 1]
    y_prob = np.clip(y_prob, 0.0, 1.0)

    auc = roc_auc_score(y_test, y_prob)
    brier = brier_score_loss(y_test, y_prob)

    # Precision / recall at a low threshold (wickets are ~5%)
    threshold = 0.05
    y_pred_binary = (y_prob >= threshold).astype(int)
    precision = precision_score(y_test, y_pred_binary, zero_division=0)
    recall = recall_score(y_test, y_pred_binary, zero_division=0)

    metrics = {
        "auc_roc": round(auc, 4),
        "brier_score": round(brier, 4),
        f"precision_at_{threshold}": round(precision, 4),
        f"recall_at_{threshold}": round(recall, 4),
        "training_seconds": round(duration, 1),
    }
    logger.info(
        "xW evaluation — AUC: %.4f, Brier: %.4f, "
        "P@%.2f: %.4f, R@%.2f: %.4f",
        auc, brier, threshold, precision, threshold, recall,
    )
    return calibrated, metrics


# ═══════════════════════════════════════════════════════════════════
# SAVE HELPERS
# ═══════════════════════════════════════════════════════════════════

def _save_model(model: Any, canonical_name: str, legacy_name: str) -> str:
    """Save model under both canonical and legacy filenames."""
    os.makedirs(MODELS_DIR, exist_ok=True)

    canonical_path = os.path.join(MODELS_DIR, canonical_name)
    legacy_path = os.path.join(MODELS_DIR, legacy_name)

    joblib.dump(model, canonical_path)
    joblib.dump(model, legacy_path)

    logger.info("Saved model: %s (+ legacy: %s)", canonical_name, legacy_name)
    return canonical_path


def _save_metadata(
    train_size: int,
    test_size: int,
    xr_metrics: Dict[str, float],
    xw_metrics: Dict[str, float],
    feature_columns: list,
) -> None:
    """Save training metadata and evaluation results to JSON."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    metadata = {
        "training_date": datetime.utcnow().isoformat(),
        "sample_size": train_size + test_size,
        "train_size": train_size,
        "test_size": test_size,
        "model_type": "LightGBM",
        "features": feature_columns,
        "xr_evaluation": xr_metrics,
        "xw_evaluation": xw_metrics,
    }

    path = os.path.join(MODELS_DIR, "metadata.json")
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Saved metadata to %s", path)


def _save_top_venues(train_df: pd.DataFrame) -> None:
    pass # No longer using venue_group 'OTHER' logic


# ═══════════════════════════════════════════════════════════════════
# MAIN TRAINING PIPELINE
# ═══════════════════════════════════════════════════════════════════

def train_models(test_cutoff: str = "2022-01-01") -> Dict[str, Any]:
    """
    Full training pipeline: load data → engineer features →
    train xR + xW → evaluate → save models + metadata.

    Args:
        test_cutoff: Matches on/after this date form the test set.

    Returns:
        Metadata dict with evaluation metrics.
    """
    overall_start = time.time()
    logger.info("=" * 60)
    logger.info("Starting xR / xW model training pipeline")
    logger.info("=" * 60)

    # ── Data ─────────────────────────────────────────────────────
    db = SessionLocal()
    try:
        full_df = build_feature_dataframe(db, min_matches=50)
        # Drop columns not needed for modeling like match_date, extras, etc.
        # But we need match_date for train_test_split_by_year
        train_df, test_df = train_test_split_by_year(full_df, test_year=int(test_cutoff[:4]))
    finally:
        db.close()

    X_train = _prepare_features(train_df)
    X_test = _prepare_features(test_df)

    y_train_xr = train_df[TARGET_XR]
    y_test_xr = test_df[TARGET_XR]

    y_train_xw = train_df[TARGET_XW]
    y_test_xw = test_df[TARGET_XW]

    logger.info(
        "Data ready — Train: %d rows, Test: %d rows",
        len(X_train), len(X_test),
    )
    logger.info(
        "Wicket rate — Train: %.2f%%, Test: %.2f%%",
        100.0 * y_train_xw.mean(),
        100.0 * y_test_xw.mean(),
    )

    # ── Train xR ─────────────────────────────────────────────────
    xr_model, xr_metrics = _train_xr(X_train, y_train_xr, X_test, y_test_xr)
    _save_model(xr_model, "xR_lgb.pkl", "xR_model.pkl")

    # ── Train xW ─────────────────────────────────────────────────
    xw_model, xw_metrics = _train_xw(X_train, y_train_xw, X_test, y_test_xw)
    _save_model(xw_model, "xW_lgb_calibrated.pkl", "xW_model.pkl")

    # ── Metadata ─────────────────────────────────────────────────
    _save_metadata(
        train_size=len(train_df),
        test_size=len(test_df),
        xr_metrics=xr_metrics,
        xw_metrics=xw_metrics,
        feature_columns=FEATURE_COLUMNS,
    )

    # ── Save top venues for predictor inference ──────────────────
    _save_top_venues(train_df)

    total_time = time.time() - overall_start
    logger.info("=" * 60)
    logger.info("Training pipeline complete in %.1fs", total_time)
    logger.info("=" * 60)

    return {
        "status": "completed",
        "training_date": datetime.utcnow().isoformat(),
        "sample_size": len(train_df) + len(test_df),
        "train_size": len(train_df),
        "test_size": len(test_df),
        "xr_evaluation": xr_metrics,
        "xw_evaluation": xw_metrics,
        "total_seconds": round(total_time, 1),
    }


# ═══════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    result = train_models()
    print("\nTraining Results:")
    print(json.dumps(result, indent=2))
