"""File storage service (local filesystem for MVP)."""

from pathlib import Path

from fastapi import HTTPException, UploadFile

from api.config import settings

CHUNK_SIZE = 1024 * 1024  # 1 MiB per read


def save_upload(file_content: bytes, filename: str, job_id: str) -> str:
    """Legacy API: save a pre-read bytes buffer. Kept for small uploads
    (e.g. revision files). Prefer `save_upload_stream` for user-uploaded DXFs."""
    upload_dir = Path(settings.upload_dir) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / filename
    dest.write_bytes(file_content)
    return str(dest)


async def save_upload_stream(
    upload: UploadFile,
    filename: str,
    job_id: str,
    max_bytes: int,
) -> str:
    """Stream an UploadFile to disk in 1 MiB chunks. Raises HTTPException(413)
    if total bytes exceed ``max_bytes``. Never loads the full file into RAM.
    """
    upload_dir = Path(settings.upload_dir) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / filename

    total = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Arquivo excede o limite de {max_bytes // (1024*1024)}MB",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return str(dest)
