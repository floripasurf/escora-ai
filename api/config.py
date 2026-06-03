"""Application configuration.

All persistent paths derive from a single `data_dir` root, resolved from
`ESCORA_DATA_DIR` on every access so tests can monkeypatch it at runtime.
In production that root is `/data` (Fly volume); locally it's `./data`.
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./escora.db"  # legacy, unused
    redis_url: str = "redis://localhost:6379"
    default_tenant_id: str = "pilot"
    # Hard cap on uploaded DXF size. ezdxf can expand a compressed DXF
    # 10-50x in RAM (entity graph + lookup tables); on a 2 GB VM anything
    # beyond ~30 MB risks an OOM kill that leaves jobs stuck.
    max_file_size_mb: int = 30
    # Wall-clock budget for a single pipeline run before we SIGKILL it.
    # Must be shorter than job_service.PROCESSING_TIMEOUT_SECONDS so the
    # subprocess kill happens *before* the watchdog flips the job to error.
    pipeline_timeout_seconds: int = 15 * 60
    # ODA File Converter can hang on valid DXFs in production. DWG is optional
    # and disabled by default; enable with ESCORA_DWG_CONVERSION_TIMEOUT_SECONDS
    # when the converter is stable enough for the deployment target.
    dwg_conversion_timeout_seconds: int = 0

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
