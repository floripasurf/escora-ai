"""FastAPI application — Escora.AI SaaS MVP."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes.jobs import router as jobs_router
from api.routes.auth import router as auth_router
from api.routes.admin import router as admin_router
from api.routes.projects import router as projects_router
from api.routes.design import router as design_router
from api.routes.drawing import router as drawing_router
from api.routes.inventory import router as inventory_router
from api.config import settings
from api.services import job_service, project_service

# Config central de logging: sem isto os logger.* espalhados dependiam da
# config default do uvicorn (nível/formato inconsistentes entre módulos).
logging.basicConfig(
    level=os.environ.get("ESCORA_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

# Observabilidade opcional: só ativa com SENTRY_DSN no ambiente (plist do
# engine). O default do sentry-sdk já captura exceções ASGI não tratadas.
if os.environ.get("SENTRY_DSN"):
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=0.0)
        logger.info("Sentry habilitado")
    except ImportError:
        logger.warning(
            "SENTRY_DSN setado mas sentry-sdk não instalado (pip install -e '.[ops]')"
        )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _startup()
    yield


app = FastAPI(title="Escora.AI", version="0.3.0", lifespan=_lifespan)

# The production frontend (https://estrutura.app) calls the engine
# cross-origin; pages served by the engine itself are same-origin.
_DEFAULT_CORS_ORIGINS = (
    "https://estrutura.app,http://localhost:8020,http://127.0.0.1:8020"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in os.environ.get("ESCORA_CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
        if o.strip()
    ],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "X-Branch-Id", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(jobs_router)
app.include_router(projects_router)
app.include_router(design_router)
app.include_router(drawing_router)
app.include_router(inventory_router)

# Serve static frontend
STATIC_DIR = Path(__file__).parent.parent / "web" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _startup() -> None:
    import shutil

    settings.ensure_dirs()

    # Seed persistent locadoras.json from the image-baked default on first boot.
    # On subsequent starts the file already exists on the volume and is left alone,
    # so password changes, new users, etc. survive restarts.
    loc_target = os.environ.get("ESCORA_LOCADORAS_FILE")
    if loc_target:
        target = Path(loc_target)
        if not target.exists():
            source = Path(__file__).parent.parent / "data" / "locadoras.json"
            if source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                logger.info(f"Seeded locadoras from {source} → {target}")

    job_service.init_db()
    swept = job_service.sweep_orphan_processing()
    if swept:
        logger.warning(f"Startup: marked {swept} orphan job(s) as error")
    project_service.init_db()
    swept_projects = project_service.sweep_orphan_processing()
    if swept_projects:
        logger.warning(f"Startup: marked {swept_projects} orphan project(s) as error")
    # Session store (SQLite) warm-up.
    from src.auth.branches import init_sessions_db, repair_default_inventory_names
    from src.auth.registry import init_registry_db
    init_registry_db()
    repair_default_inventory_names()
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
