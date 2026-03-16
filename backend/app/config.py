"""
Application configuration using Pydantic Settings.
"""

from pydantic import field_validator
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
    app_name: str = "Mundaneum"
    debug: bool = False
    log_level: str = "INFO"

    # CORS origins (comma-separated in env)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Database
    database_url: str = "postgresql://mundaneum:mundaneum@localhost:5432/mundaneum"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # Meilisearch
    meili_url: str = "http://localhost:7700"
    meili_api_key: str | None = None
    meili_timeout: int = 10

    # MinIO (future use)
    minio_url: str = "localhost:9000"
    minio_access_key: str = "mundaneum"
    minio_secret_key: str = "mundaneumpass"

    # Bibliography source
    bibliography_repo_url: str = "https://github.com/b-vitamins/bibliography/"
    bibliography_checkout_path: str = "/tmp/mundaneum/bibliography"
    bibliography_repo_ref: str | None = None
    bibliography_sync_timeout_seconds: int = 300
    bibliography_runtime_sync_enabled: bool = True

    # Semantic Scholar
    s2_api_key: str | None = None
    s2_max_edges: int = 500
    s2_staleness_days: int = 7
    s2_rate_limit: float = 0.9  # reqs/sec without key (with key: auto 10.0)
    s2_backfill_batch_size: int = 10
    s2_backfill_initial_delay_seconds: int = 30
    s2_backfill_idle_delay_seconds: int = 300
    s2_backfill_batch_delay_seconds: int = 5
    s2_backfill_error_delay_seconds: int = 60

    # NER Signals
    ner_signals_path: str = "/data/ner/signals-product"
    ner_auto_ingest_enabled: bool = True
    ner_auto_ingest_wait_for_entries: bool = True
    ner_auto_ingest_wait_timeout_seconds: int = 1800
    ner_auto_ingest_poll_interval_seconds: float = 5.0

    # S2 corpus pipeline (local dataset cache)
    s2_corpus_path: str = "/data/s2/corpus.duckdb"
    s2_shards_path: str = "/data/s2/shards"
    s2_minio_bucket: str = "s2-corpus"
    s2_qdrant_url: str = "http://localhost:6333"
    s2_qdrant_api_key: str | None = None

    @field_validator(
        "meili_api_key",
        "s2_api_key",
        "s2_qdrant_api_key",
        "bibliography_repo_ref",
        mode="before",
    )
    @classmethod
    def blank_optional_values_are_none(cls, value: str | None) -> str | None:
        """Normalize empty env-file secrets to None instead of empty strings."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
