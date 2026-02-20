"""
Application configuration using Pydantic Settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

# Application version
VERSION = "0.1.0"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Folio"
    debug: bool = False
    log_level: str = "INFO"

    # CORS origins (comma-separated in env)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Database
    database_url: str = "postgresql://folio:folio@localhost:5432/folio"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # Meilisearch
    meili_url: str = "http://localhost:7700"
    meili_api_key: str | None = None
    meili_timeout: int = 10

    # MinIO (future use)
    minio_url: str = "localhost:9000"
    minio_access_key: str = "folio"
    minio_secret_key: str = "foliopass"

    # Data directory
    bib_directory: str = "/data"

    # Semantic Scholar
    s2_api_key: str | None = None
    s2_max_edges: int = 500
    s2_staleness_days: int = 7
    s2_rate_limit: float = 0.9  # reqs/sec without key (with key: auto 10.0)

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
