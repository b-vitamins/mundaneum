"""
CLI entrypoint for the S2 dataset ingestion pipeline.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback

from app.services.s2_ingest_config import ALL_DATASETS, CORE_DATASETS, load_settings
from app.services.s2_ingest_download import download_dataset
from app.services.s2_ingest_duckdb import (
    build_indexes,
    find_shards,
    get_status,
    ingest_dataset,
)

logger = logging.getLogger(__name__)


def _dataset_args(raw: str, include_all: bool) -> list[str]:
    if include_all:
        return ALL_DATASETS
    return [dataset.strip() for dataset in raw.split(",") if dataset.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="S2 Academic Graph dataset pipeline",
        prog="s2_ingest",
    )
    sub = parser.add_subparsers(dest="command")

    download = sub.add_parser("download", help="Download dataset shards from S2")
    download.add_argument(
        "--datasets",
        type=str,
        default=",".join(CORE_DATASETS),
        help="Comma-separated dataset names (default: core datasets)",
    )
    download.add_argument(
        "--all",
        action="store_true",
        dest="all_datasets",
        help="Download ALL datasets (including embeddings + full-text)",
    )
    download.add_argument("--release", type=str, help="Release date (default: latest)")

    ingest = sub.add_parser("ingest", help="Ingest downloaded shards into DuckDB")
    ingest.add_argument(
        "--datasets",
        type=str,
        default=",".join(CORE_DATASETS),
        help="Comma-separated dataset names to ingest",
    )
    ingest.add_argument(
        "--all",
        action="store_true",
        dest="all_datasets",
        help="Ingest ALL downloaded datasets",
    )
    ingest.add_argument("--no-index", action="store_true", help="Skip index building")

    sub.add_parser("status", help="Show pipeline status")
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args()
    settings = load_settings()

    shards_dir = settings.shards_path
    db_path = settings.corpus_path

    if args.command == "download":
        if not settings.api_key:
            logger.error("S2_API_KEY is required for downloading datasets. Set it in .env")
            sys.exit(1)

        datasets = _dataset_args(args.datasets, args.all_datasets)
        for dataset in datasets:
            try:
                download_dataset(dataset, shards_dir, settings.api_key, args.release)
            except Exception as exc:
                logger.error("Failed to download '%s': %s", dataset, exc)
        return

    if args.command == "ingest":
        db_path.parent.mkdir(parents=True, exist_ok=True)
        datasets = _dataset_args(args.datasets, args.all_datasets)

        for dataset in datasets:
            shards = find_shards(shards_dir, dataset)
            if not shards:
                logger.warning("No shards found for '%s' — download first", dataset)
                continue
            try:
                ingest_dataset(dataset, shards, db_path)
            except Exception as exc:
                logger.error("Failed to ingest '%s': %s", dataset, exc)
                traceback.print_exc()

        if not args.no_index:
            build_indexes(db_path)

        logger.info("Done. DuckDB size: %.2f GB", db_path.stat().st_size / 1024**3)
        return

    if args.command == "status":
        print(json.dumps(get_status(db_path, shards_dir), indent=2))
        return

    parser.print_help()
