import os
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
import lightgbm as lgb
from database import SessionLocal
from ml.feature_engineering import build_feature_dataframe, train_test_split_by_year

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODELS_DIR, exist_ok=True)

def train_xw_model(test_year: int = 2024):
    db = SessionLocal()
    try:
        df = build_feature_dataframe(db)
        train_df, test_df = train_test_split_by_year(df, test_year=test_year)
    finally:
        db.close()

    features = [
        "batting_position", "phase", "ball_number", "is_pace", "venue", 
        "shot_intent", "pitch_zone", "computed_false_shot"
    ]
    target = "target_xW"

    X_train = train_df[features]
    y_train = train_df[target]
    X_test = test_df[features]
    y_test = test_df[target]

    base_model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=50,
        is_unbalance=True,
        random_state=42
    )

    calibrated_model = CalibratedClassifierCV(base_model, cv=5, method="isotonic")

    print("Training and calibrating xW model...")
    calibrated_model.fit(X_train, y_train)

    if X_test.empty:
        print("Warning: Test set is empty. Skipping evaluation.")
    else:
        print("Evaluating xW model...")
        y_pred_proba = calibrated_model.predict_proba(X_test)[:, 1]
        
        auc = roc_auc_score(y_test, y_pred_proba)
        brier = brier_score_loss(y_test, y_pred_proba)
        ll = log_loss(y_test, y_pred_proba)
        
        print(f"AUC-ROC:    {auc:.4f}")
        print(f"Brier Score: {brier:.4f}")
        print(f"Log Loss:    {ll:.4f}")

        print("\nCalibration Curve Summary:")
        prob_true, prob_pred = calibration_curve(y_test, y_pred_proba, n_bins=10)
        for p_true, p_pred in zip(prob_true, prob_pred):
            print(f"  Predicted: {p_pred:.4f} -> Actual: {p_true:.4f}")

    return calibrated_model

if __name__ == "__main__":
    calibrated_model = train_xw_model()
    model_path = os.path.join(MODELS_DIR, "xW_lgb_calibrated.pkl")
    joblib.dump(calibrated_model, model_path)
    print(f"Saved calibrated model to {model_path}")
