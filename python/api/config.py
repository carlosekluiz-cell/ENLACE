"""
ENLACE API Configuration

Pydantic Settings class for environment-based configuration.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database (async)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "enlace"
    postgres_user: str = "enlace"
    postgres_password: str = "enlace_dev_2026"

    @property
    def database_url(self) -> str:
        """Async database URL for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_sync_url(self) -> str:
        """Synchronous database URL for migrations and scripts."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_url: str = "redis://localhost:6379"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "enlace_minio"
    minio_root_password: str = "enlace_minio_2026"
    minio_secure: bool = False

    # JWT Authentication
    jwt_secret_key: str = "change-this-to-random-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # RF Engine (Rust gRPC service)
    rf_engine_host: str = "localhost"
    rf_engine_port: int = 50051

    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]

    # Application
    app_name: str = "ENLACE API"
    app_version: str = "1.0.0"
    debug: bool = False
    default_country: str = "BR"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton settings instance
settings = Settings()
