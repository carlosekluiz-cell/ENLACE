"""
ENLACE API Configuration

Pydantic Settings class for environment-based configuration.

Security: All secrets default to empty strings. In production (DEV_MODE != "1"),
a RuntimeError is raised at startup if any required secret is not set via
environment variables or .env file.
"""

import os
import warnings

from pydantic_settings import BaseSettings
from typing import List

# ---------------------------------------------------------------------------
# Secret helpers
# ---------------------------------------------------------------------------

_DEV_MODE = os.getenv("DEV_MODE", "1").strip().lower() in ("1", "true", "yes")


def _require_secret(env_var: str, dev_default: str = "") -> str:
    """Get a secret from environment. In production, raises if not set."""
    value = os.getenv(env_var, "")
    if not value:
        if _DEV_MODE:
            if dev_default:
                warnings.warn(f"{env_var} not set, using dev default", stacklevel=2)
                return dev_default
            raise RuntimeError(f"{env_var} must be set")
        raise RuntimeError(f"{env_var} must be set in production (DEV_MODE=0)")
    return value


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database (async)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "enlace"
    postgres_user: str = "enlace"
    postgres_password: str = ""

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
    minio_root_password: str = ""
    minio_secure: bool = False

    # JWT Authentication
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # RF Engine (Rust gRPC service)
    rf_engine_host: str = "localhost"
    rf_engine_port: int = 50051

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:4100"]

    # Application
    app_name: str = "ENLACE API"
    app_version: str = "1.0.0"
    debug: bool = False
    default_country: str = "BR"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()


def validate_secrets() -> None:
    """Validate that all required secrets are set.

    In production (DEV_MODE != "1"), raises RuntimeError if any secret
    environment variable is missing or empty.
    """
    _secrets = {
        "POSTGRES_PASSWORD": settings.postgres_password,
        "MINIO_ROOT_PASSWORD": settings.minio_root_password,
        "JWT_SECRET_KEY": settings.jwt_secret_key,
    }
    missing = [k for k, v in _secrets.items() if not v]
    if missing:
        if _DEV_MODE:
            for name in missing:
                warnings.warn(
                    f"Secret {name} is not set. This is acceptable in dev mode "
                    f"but MUST be configured for production.",
                    stacklevel=2,
                )
        else:
            raise RuntimeError(
                f"The following secrets must be set in production "
                f"(DEV_MODE=0): {', '.join(missing)}. "
                f"Set them in environment variables or .env file."
            )


# Run validation at import time
validate_secrets()
