"""
Compatibility surface for the S2 dataset ingestion pipeline.

The implementation now lives in dedicated modules for config, download,
DuckDB ingestion, and CLI orchestration.
"""

from app.services.s2_ingest_cli import main
from app.services.s2_ingest_config import (
    ALL_DATASETS,
    CORE_DATASETS,
    S2_DATASETS_API,
    URL_REFRESH_INTERVAL as _URL_REFRESH_INTERVAL,
    load_settings as _load_settings,
)
from app.services.s2_ingest_download import (
    download_dataset,
    download_shard,
    get_download_links,
    get_latest_release,
)
from app.services.s2_ingest_duckdb import (
    build_indexes,
    find_shards as _find_shards,
    get_status,
    ingest_dataset,
)

__all__ = [
    "ALL_DATASETS",
    "CORE_DATASETS",
    "S2_DATASETS_API",
    "_URL_REFRESH_INTERVAL",
    "_find_shards",
    "_load_settings",
    "build_indexes",
    "download_dataset",
    "download_shard",
    "get_download_links",
    "get_latest_release",
    "get_status",
    "ingest_dataset",
    "main",
]


if __name__ == "__main__":
    main()
