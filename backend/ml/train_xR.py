import os
import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import lightgbm as lgb
from database import SessionLocal
from ml.feature_engineering import build_feature_dataframe, train_test_split_by_year

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODELS_DIR, exist_ok=True)

def train_xr_model(test_year: int = 2024):
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
    target = "target_xR"

    X_train = train_df[features]
    y_train = train_df[target]
    X_test = test_df[features]
    y_test = test_df[target]

    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=50,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )

    print("Training xR model...")
    model.fit(X_train, y_train)

    import numpy as np
    if X_test.empty:
        print("Warning: Test set is empty (no matches >= test_year). Skipping evaluation.")
    else:
        print("Evaluating xR model...")
        y_pred = model.predict(X_test)
        
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        
        print(f"MAE:  {mae:.4f}")
        print(f"RMSE: {rmse:.4f}")
        print(f"R²:   {r2:.4f}")

    print("\nFeature Importances (Top 10):")
    importance_df = pd.DataFrame({
        "Feature": features,
        "Importance": model.feature_importances_
    }).sort_values(by="Importance", ascending=False).head(10)
    for _, row in importance_df.iterrows():
        print(f"  {row['Feature']}: {row['Importance']}")

    return model

if __name__ == "__main__":
    model = train_xr_model()
    model_path = os.path.join(MODELS_DIR, "xR_lgb.pkl")
    joblib.dump(model, model_path)
    print(f"Saved model to {model_path}")
