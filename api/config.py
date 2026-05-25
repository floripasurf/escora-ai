"""Application configuration.

All persistent paths derive from a single `data_dir` root, resolved from
`ESCORA_DATA_DIR` on every access so tests can monkeypatch it at runtime.
In production that root is `/data` (Fly volume); locally it's `./data`.
"""

import logging
import os
from pathlib import Path

from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)

_REDIS_DEV_DEFAULT = "redis://localhost:6379"


class Settings(BaseSettings):
    database_url: str = "sqlite:///./escora.db"  # legacy, unused
    redis_url: str = _REDIS_DEV_DEFAULT
    default_tenant_id: str = "pilot"
    # Hard cap on uploaded DXF size. ezdxf can expand a compressed DXF
    # 10-50x in RAM (entity graph + lookup tables); on a 2 GB VM anything
    # beyond ~30 MB risks an OOM kill that leaves jobs stuck.
    max_file_size_mb: int = 30
    # Wall-clock budget for a single pipeline run before we SIGKILL it.
    # Must be shorter than job_service.PROCESSING_TIMEOUT_SECONDS so the
    # subprocess kill happens *before* the watchdog flips the job to error.
    pipeline_timeout_seconds: int = 8 * 60

    class Config:
        env_file = ".env"

    # --- Paths (resolved lazily from env) ---

    @property
    def data_root(self) -> Path:
        return Path(os.environ.get("ESCORA_DATA_DIR", "./data"))

    @property
    def upload_dir(self) -> str:
        return str(self.data_root / "uploads")

    @property
    def output_dir(self) -> str:
        return str(self.data_root / "output")

    @property
    def jobs_db_path(self) -> Path:
        return self.data_root / "jobs.db"

    @property
    def learning_dir(self) -> Path:
        return self.data_root / "learning"

    def ensure_dirs(self) -> None:
        for p in (self.upload_dir, self.output_dir, self.learning_dir):
            Path(p).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()

# Defensive: when running in production, the localhost Redis default almost
# certainly means a missed env var. Warn loudly so it shows up in deploy logs.
if os.environ.get("ESCORA_ENV", "").lower() == "prod" and settings.redis_url == _REDIS_DEV_DEFAULT:
    _logger.warning(
        "ESCORA_ENV=prod but REDIS_URL still defaults to %s — set REDIS_URL "
        "before any background-job work.",
        _REDIS_DEV_DEFAULT,
    )
