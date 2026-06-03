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

# ── Manual Migration ─────────────────────────────────────────────
# Add gender column if it does not exist (SQLite safe approach via try/except)
from sqlalchemy import text
with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE matches ADD COLUMN gender VARCHAR(10) NOT NULL DEFAULT 'male'"))
    except Exception:
        pass  # Column likely already exists

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

# ── Lifecycle ────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    import asyncio
    from service.ai_analyst import prewarm_models
    # Run synchronously blocking request in a separate thread so server boots immediately
    asyncio.create_task(asyncio.to_thread(prewarm_models))
