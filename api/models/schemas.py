"""Pydantic request/response schemas."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class JobCreateResponse(BaseModel):
    id: str
    status: str
    filename: str
    created_at: datetime


class JobStatusResponse(BaseModel):
    id: str
    status: str
    filename: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class JobPreviewResponse(BaseModel):
    id: str
    elements: List[dict]
    warnings: List[str]
    scale: float
    pe_direito_m: Optional[float]
