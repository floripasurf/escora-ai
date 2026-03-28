"""Pydantic request/response schemas."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class JobCreateResponse(BaseModel):
    id: str
    status: str
    filename: str
    created_at: datetime


class BeamResult(BaseModel):
    name: Optional[str] = None
    length_m: float
    width_m: float
    height_m: Optional[float] = None
    shore_count: int
    spacing_m: float


class SlabResult(BaseModel):
    area_m2: float
    thickness_m: float
    shore_count: int
    grid: str


class JobStatusResponse(BaseModel):
    id: str
    status: str
    filename: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Results (filled when status == "done")
    beam_count: Optional[int] = None
    pillar_count: Optional[int] = None
    slab_count: Optional[int] = None
    total_shores: Optional[int] = None
    beams: Optional[List[BeamResult]] = None
    slabs: Optional[List[SlabResult]] = None
    warnings: Optional[List[str]] = None
    has_output_dxf: bool = False
    has_csv: bool = False
    has_revision: bool = False
    revision_learnings: Optional[List[str]] = None
