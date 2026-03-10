"""
Configuration and constants for the S2 dataset ingestion pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


S2_DATASETS_API = "https://api.semanticscholar.org/datasets/v1"

CORE_DATASETS = [
    "papers",
    "citations",
    "authors",
    "abstracts",
    "tldrs",
    "paper-ids",
    "publication-venues",
]

ALL_DATASETS = CORE_DATASETS + [
    "embeddings-specter_v2",
    "s2orc_v2",
]

URL_REFRESH_INTERVAL = 30 * 60


@dataclass(frozen=True, slots=True)
class S2IngestSettings:
    api_key: str | None
    shards_path: Path
    corpus_path: Path


def load_settings() -> S2IngestSettings:
    """Load settings outside the FastAPI runtime as well as inside it."""
    try:
        from app.config import settings

        return S2IngestSettings(
            api_key=settings.s2_api_key,
            shards_path=Path(settings.s2_shards_path),
            corpus_path=Path(settings.s2_corpus_path),
        )
    except Exception:
        from dotenv import dotenv_values

        env = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
        return S2IngestSettings(
            api_key=env.get("S2_API_KEY"),
            shards_path=Path(env.get("S2_SHARDS_PATH", "/data/s2/shards")),
            corpus_path=Path(env.get("S2_CORPUS_PATH", "/data/s2/corpus.duckdb")),
        )
