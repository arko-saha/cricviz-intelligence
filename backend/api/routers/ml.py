import os
import uuid
import shutil
import joblib
from datetime import datetime
from fastapi import APIRouter, Header, HTTPException, BackgroundTasks
from pydantic import BaseModel
from database import SessionLocal
from sqlalchemy import text
from ml.predictor import XR_MODEL_PATH, XW_MODEL_PATH, MODELS_DIR
from service.enrichment import predictor

router = APIRouter()

class RetrainRequest(BaseModel):
    target: str
    test_year: int = 2024

def retrain_task(target: str, test_year: int):
    # Archive models
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = os.path.join(MODELS_DIR, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    
    if target in ("xR", "both") and os.path.exists(XR_MODEL_PATH):
        shutil.copy(XR_MODEL_PATH, os.path.join(archive_dir, f"xR_lgb_{timestamp}.pkl"))
    if target in ("xW", "both") and os.path.exists(XW_MODEL_PATH):
        shutil.copy(XW_MODEL_PATH, os.path.join(archive_dir, f"xW_lgb_{timestamp}.pkl"))

    # Train and Atomic Replace
    try:
        if target in ("xR", "both"):
            from ml.train_xR import train_xr_model
            xr_model = train_xr_model(test_year=test_year)
            temp_path = XR_MODEL_PATH + ".tmp"
            joblib.dump(xr_model, temp_path)
            os.replace(temp_path, XR_MODEL_PATH)
            
        if target in ("xW", "both"):
            from ml.train_xW import train_xw_model
            xw_model = train_xw_model(test_year=test_year)
            temp_path = XW_MODEL_PATH + ".tmp"
            joblib.dump(xw_model, temp_path)
            os.replace(temp_path, XW_MODEL_PATH)
    finally:
        # Reload predictor singleton
        predictor.reload()

@router.post("/retrain")
def retrain_models(req: RetrainRequest, background_tasks: BackgroundTasks, x_admin_key: str = Header(None)):
    expected_key = os.getenv("ADMIN_KEY", "secret-admin-key")
    if not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    if req.target not in ("xR", "xW", "both"):
        raise HTTPException(status_code=400, detail="target must be xR, xW, or both")
        
    job_id = str(uuid.uuid4())
    background_tasks.add_task(retrain_task, req.target, req.test_year)
    
    return {"status": "started", "job_id": job_id, "target": req.target}

@router.get("/model-info")
def get_model_info():
    info = {"models_active": predictor.models_available}
    for name, path in [("xR", XR_MODEL_PATH), ("xW", XW_MODEL_PATH)]:
        if os.path.exists(path):
            stat = os.stat(path)
            info[name] = {
                "exists": True,
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "file_size_kb": round(stat.st_size / 1024.0, 2)
            }
        else:
            info[name] = {"exists": False, "mtime": None, "file_size_kb": 0.0}
    return info

@router.get("/training-data-stats")
def get_training_stats():
    db = SessionLocal()
    try:
        # total_deliveries
        total = db.execute(text("SELECT COUNT(*) FROM deliveries")).scalar()
        
        # deliveries_with_commentary
        with_comm = db.execute(text("SELECT COUNT(*) FROM deliveries WHERE commentary_text IS NOT NULL AND commentary_text != ''")).scalar()
        
        # deliveries_with_shot_intent
        with_intent = db.execute(text("SELECT COUNT(*) FROM cricviz_metrics WHERE shot_intent IS NOT NULL AND shot_intent != 'UNKNOWN'")).scalar()
        
        # match_date_range
        date_range = db.execute(text("SELECT MIN(date), MAX(date) FROM matches")).fetchone()
        
        return {
            "total_deliveries": total or 0,
            "deliveries_with_commentary": with_comm or 0,
            "deliveries_with_shot_intent": with_intent or 0,
            "match_date_range": {
                "min": str(date_range[0]) if date_range and date_range[0] else None,
                "max": str(date_range[1]) if date_range and date_range[1] else None
            }
        }
    finally:
        db.close()
