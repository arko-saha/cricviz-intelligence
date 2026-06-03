"""
Application configuration — centralised settings for all layers.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# ── Paths ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
DB_PATH  = BASE_DIR / "cricviz.db"

# ── Database ─────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DB_PATH}"
)

# SQLAlchemy engine kwargs — pool settings are PostgreSQL-specific;
# SQLite uses NullPool by default so these are only applied for PG.
POOL_TIMEOUT  = 30
POOL_RECYCLE  = 1800
POOL_SIZE     = 5
POOL_MAX_OVERFLOW = 10

# ── Celery ───────────────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# ── Auth ─────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_dev_key_do_not_use_in_prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# ── API ──────────────────────────────────────────────────────────
API_VERSION = "1.0.0"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# ── HuggingFace AI ───────────────────────────────────────────────
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")

if not HF_API_TOKEN:
    raise EnvironmentError(
        "HF_API_TOKEN is not set or is still a placeholder.\n"
        "Get a free token at: huggingface.co/settings/tokens\n"
        "Add it to your .env file. Never commit it to git."
    )

HF_PRIMARY_MODEL = os.getenv("HF_PRIMARY_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
HF_MAX_NEW_TOKENS = int(os.getenv("HF_MAX_NEW_TOKENS", "400"))
HF_TEMPERATURE = float(os.getenv("HF_TEMPERATURE", "0.7"))
HF_TIMEOUT_SECONDS = int(os.getenv("HF_TIMEOUT_SECONDS", "35"))

HF_MODEL_ROSTER = [
    # Tier 1 — Best instruction-following, strong reasoning
    "mistralai/Mistral-7B-Instruct-v0.3",       # Primary: best free all-rounder
    "mistralai/Mistral-7B-Instruct-v0.2",       # Fallback A: stable older version

    # Tier 2 — Strong coding + analytical text generation
    "Qwen/Qwen2.5-Coder-7B-Instruct",           # Fallback B: best free coding model
    "microsoft/Phi-3.5-mini-instruct",           # Fallback C: small, fast, reliable

    # Tier 3 — Last resort, widely available on free tier
    "HuggingFaceH4/zephyr-7b-beta",             # Fallback D: stable, well-tested
    "tiiuae/falcon-7b-instruct",                 # Fallback E: emergency last resort
]

# ── CricAPI ──────────────────────────────────────────────────────
CRICAPI_KEY = os.getenv("CRICAPI_KEY", "")

# ── Ingestion ────────────────────────────────────────────────────
CRICSHEET_DEFAULT_URL = "https://cricsheet.org/downloads/t20s_json.zip"
