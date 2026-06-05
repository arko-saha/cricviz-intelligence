"""
CricViz Intelligence Dashboard — FastAPI Entry Point.

Creates tables, configures CORS, and mounts the API router.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine
from models import Base
from api.routes import router

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

# ── Create tables ────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── Migrations ───────────────────────────────────────────────────
# Schema migrations are managed by Alembic.  Run:
#   alembic upgrade head
# See alembic/versions/ for the migration history.

# ── App ──────────────────────────────────────────────────────────
app = FastAPI(
    title="CricViz Intelligence Dashboard",
    description="Cricket analytics platform powered by Cricsheet data and CricViz-style enrichment",
    version="1.0.0",
)

# ── CORS ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routes ─────────────────────────────────────────────────
app.include_router(router, prefix="/api")

from api.routers.ml import router as ml_router
app.include_router(ml_router, prefix="/api/v1/ml", tags=["ML"])

from api.routers.admin import router as admin_router
app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])

# ── Lifecycle ────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    import asyncio
    from service.ai_analyst import prewarm_models
    from ingestion.player_registry import ensure_registry_fresh
    from database import SessionLocal
    
    # Run synchronously blocking request in a separate thread so server boots immediately
    asyncio.create_task(asyncio.to_thread(prewarm_models))
    
    # Ensure player registry is populated and fresh
    def check_registry():
        db = SessionLocal()
        try:
            ensure_registry_fresh(db)
        finally:
            db.close()
            
    asyncio.create_task(asyncio.to_thread(check_registry))


