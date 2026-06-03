@echo off
echo Starting CricViz Intelligence Dashboard Services...
echo =================================================

REM Check if Redis is running (optional but good practice)
echo Make sure Redis is running for Celery!
echo.

echo Starting Celery Worker...
start "Celery Worker" cmd /c "cd backend && celery -A worker.celery_app worker --loglevel=info"

echo Starting FastAPI Backend...
start "FastAPI Backend" cmd /c "cd backend && uvicorn main:app --reload"

echo Starting Vite React Frontend...
start "React Frontend" cmd /c "cd frontend && npm run dev"

echo All services have been launched in separate windows!
echo - Frontend: http://localhost:5173
echo - Backend API: http://localhost:8000/docs
echo.
pause
