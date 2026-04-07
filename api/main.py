"""FastAPI application — Escora.AI SaaS MVP."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes.jobs import router as jobs_router
from api.routes.auth import router as auth_router
from api.config import settings

app = FastAPI(title="Escora.AI", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(jobs_router)

# Serve static frontend
STATIC_DIR = Path(__file__).parent.parent / "web" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/api/v1/health")
def health():
    from api.services.job_service import _jobs
    return {
        "status": "ok",
        "jobs_count": len(_jobs),
        "version": "0.2.0",
    }


@app.get("/")
async def index():
    """Serve the single-page frontend."""
    index_path = Path(__file__).parent.parent / "web" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return {"message": "Escora.AI API — frontend not found, use /api/v1/health"}
