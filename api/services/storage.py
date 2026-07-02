"""File storage service (local filesystem for MVP)."""

import re
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile

from api.config import settings

CHUNK_SIZE = 1024 * 1024  # 1 MiB per read


def sanitize_filename(filename: str, default: str = "upload.dxf") -> str:
    """Strip any path components and normalize the stem to a safe charset.

    The client-supplied filename lands directly under the job's upload dir;
    without this a name like ``../../x.dxf`` would escape it.
    """
    name = Path(filename or "").name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("._")[:80]
    suffix = Path(name).suffix.lower()
    if not stem:
        return default
    return f"{stem}{suffix}"


def save_upload(file_content: bytes, filename: str, job_id: str) -> str:
    """Legacy API: save a pre-read bytes buffer. Kept for small uploads
    (e.g. revision files). Prefer `save_upload_stream` for user-uploaded DXFs."""
    upload_dir = Path(settings.upload_dir) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / sanitize_filename(filename)
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
    dest = upload_dir / sanitize_filename(filename)

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


async def read_upload_capped(upload: UploadFile, max_bytes: int) -> bytes:
    """Read an UploadFile fully into memory, bounded by ``max_bytes``.

    For parsers that need the raw bytes (CSV/XLSX import). Raises
    HTTPException(413) instead of buffering an arbitrarily large body.
    """
    buf = bytearray()
    while True:
        chunk = await upload.read(CHUNK_SIZE)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Arquivo excede o limite de {max_bytes // (1024*1024)}MB",
            )
    return bytes(buf)
