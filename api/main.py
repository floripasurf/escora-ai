"""FastAPI application — Escora.AI SaaS MVP."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.deps import get_current_branch
from api.routes.jobs import router as jobs_router
from api.routes.auth import router as auth_router
from api.routes.projects import router as projects_router
from api.routes.design import router as design_router
from api.routes.drawing import router as drawing_router
from api.config import settings
from api.services import job_service
from api.services import project_store

logger = logging.getLogger(__name__)

app = FastAPI(title="Escora.AI", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://estrutura.app",
        "https://www.estrutura.app",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    # Inline scripts/styles are still present in the static MVP frontend.
    # Escora-2 should move them to static files and remove 'unsafe-inline'.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://escora-ai.fly.dev https://estrutura.app https://www.estrutura.app; "
        "frame-ancestors 'none'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response

app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(projects_router, dependencies=[Depends(get_current_branch)])
app.include_router(design_router, dependencies=[Depends(get_current_branch)])
app.include_router(drawing_router, dependencies=[Depends(get_current_branch)])

# Serve static frontend
STATIC_DIR = Path(__file__).parent.parent / "web" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def _startup() -> None:
    settings.ensure_dirs()

    job_service.init_db()
    project_store.init_db()
    swept = job_service.sweep_orphan_processing()
    if swept:
        logger.warning(f"Startup: marked {swept} orphan job(s) as error")
    # Session store (SQLite) warm-up.
    from src.auth.branches import init_sessions_db
    init_sessions_db()


@app.get("/api/v1/health")
def health():
    jobs = job_service.all_jobs()
    return {
        "status": "ok",
        "jobs_count": len(jobs),
        "version": "0.3.0",
        "data_dir": str(settings.data_root),
    }


@app.get("/")
async def index():
    """Serve the single-page frontend."""
    index_path = Path(__file__).parent.parent / "web" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return {"message": "Escora.AI API — frontend not found, use /api/v1/health"}


@app.get("/projetos.html")
async def projetos():
    """Serve the masonry project generator frontend."""
    path = Path(__file__).parent.parent / "web" / "projetos.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return {"message": "Projetos frontend not found"}


@app.get("/design")
async def design():
    """Serve the interactive design editor."""
    path = Path(__file__).parent.parent / "web" / "design.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return {"message": "Design editor not found"}
