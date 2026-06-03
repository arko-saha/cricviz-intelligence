# CricViz Intelligence Dashboard

A production-grade cricket analytics platform powered by real Cricsheet data, a Python/FastAPI backend, a React frontend, and a custom CricViz-style enrichment engine (xR, xW, shot intent).

## Architecture

The project adheres strictly to a 6-layer architecture:
`Presentation (React) → API (FastAPI) → Service (Business Logic) → Repository (SQLAlchemy) → Database (SQLite/Postgres) ← Ingestion Engine`

### File Structure
```text
CricViz/
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Env vars and pool config
│   ├── database.py             # SQLAlchemy engine setup
│   ├── models.py               # ORM definitions (matches, players, deliveries, cricviz_metrics)
│   ├── api/                    # HTTP layer (routes, schemas)
│   ├── service/                # Business logic & enrichment engine
│   ├── repository/             # DB aggregations & CRUD
│   ├── ingestion/              # Cricsheet JSON/ZIP parser & CSV loader
│   └── tests/                  # Unit tests for enrichment logic
└── frontend/
    ├── index.html              # Vite entry point
    ├── src/
    │   ├── main.jsx            # React 19 root
    │   ├── App.jsx             # React Router
    │   ├── index.css           # Vanilla CSS design system
    │   ├── api/client.js       # Axios wrapper
    │   ├── store/uiStore.js    # Zustand state
    │   ├── components/         # Reusable UI (MetricCard, Navbar, etc.)
    │   ├── charts/             # Recharts (WormChart, HeatmapGrid, etc.)
    │   └── pages/              # The 3 Pillars (Match, Player, Pipeline)
```

## Local Development Setup

### 1. Backend Setup
Requires Python 3.9+.

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

pip install -r requirements.txt

# Start the FastAPI server (creates SQLite DB automatically)
uvicorn main:app --reload --port 8000
```

**Environment Variables (Optional)**:
- `DATABASE_URL`: Override the default `sqlite:///cricviz.db` with a PostgreSQL URL.
- `HF_API_TOKEN`: Set your HuggingFace Inference API token to enable the AI Analyst panel (free tier fallback chain implemented).

### 2. Frontend Setup
Requires Node.js 18+.

```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

## Data Ingestion

The platform supports two types of ingestion via the **Pipeline Control** dashboard:
1. **Cricsheet JSON ZIP**: Provide a local path or URL (e.g., `https://cricsheet.org/downloads/t20s_json.zip`). The backend stream-unpacks the ZIP, parsing metadata and deliveries into the DB without exhausting RAM.
2. **CSV Bulk Loader**: Provide a local path to `consolidated_t20_data.csv`.

**Process**:
- Go to `http://localhost:5173/ingest`
- Click "T20 Internationals" or paste a URL.
- Click "Start Ingestion". Watch the real-time background task feed.

## Running Tests

The enrichment engine is fully unit-tested (36 test cases spanning edge cases, token conflicts, and type safeguards).

```bash
cd backend
pytest tests/test_enrichment.py -v
```

## Known Limitations / Future Work

- **Commentary Dependency**: Currently, Cricsheet data does not reliably contain textual commentary. The enrichment engine falls back to run/wicket-based heuristic inference for Shot Intent and Pitch Zone. A future integration with a live API (e.g., CricAPI) providing ball-by-ball commentary strings would instantly activate the NLP-based token parsing.
- **PostgreSQL Migration**: The app currently defaults to SQLite for zero-config local development. To run in production, replace the connection string and run Alembic migrations.
- **Player Search**: The UI currently links to players via the Match Delivery Explorer. A global search bar in the Navbar would improve navigation.
