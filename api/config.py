"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./escora.db"  # MVP: SQLite, Fase 2: PostgreSQL
    redis_url: str = "redis://localhost:6379"
    upload_dir: str = "./uploads"
    output_dir: str = "./output"
    default_tenant_id: str = "pilot"  # Single-tenant MVP
    max_file_size_mb: int = 200  # Max upload size (DXFs can be huge)

    class Config:
        env_file = ".env"


settings = Settings()
