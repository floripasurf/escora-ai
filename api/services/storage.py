"""File storage service (local filesystem for MVP)."""

from pathlib import Path
from api.config import settings


def save_upload(file_content: bytes, filename: str, job_id: str) -> str:
    upload_dir = Path(settings.upload_dir) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / filename
    dest.write_bytes(file_content)
    return str(dest)
