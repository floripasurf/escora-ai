"""SQLAlchemy models for Escora.AI."""

from sqlalchemy import Column, String, Float, Integer, JSON, DateTime, Enum as SAEnum, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import enum

Base = declarative_base()


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    APPROVED = "approved"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="pilot")
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING)
    filename = Column(String, nullable=False)
    office_name = Column(String, nullable=True)
    input_path = Column(String, nullable=False)
    scale = Column(Float, nullable=True)
    pe_direito_m = Column(Float, nullable=True)
    preview_data = Column(JSON, nullable=True)
    results_data = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CatalogEntry(Base):
    __tablename__ = "catalog"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="pilot")
    manufacturer = Column(String)
    model = Column(String)
    type = Column(String, default="telescopic")
    height_min_m = Column(Float)
    height_max_m = Column(Float)
    load_capacity_kn = Column(Float)
    weight_kg = Column(Float)
    price_reference_brl = Column(Float)
    stock_quantity = Column(Integer, default=0)
    notes = Column(String, default="")
