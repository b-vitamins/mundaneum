"""
DuckDB ingestion and optimization helpers for S2 datasets.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from app.services.s2_ingest_specs import (
    CREATE_TABLES_SQL,
    DATASET_SPECS,
    SORT_OPTIMIZATIONS,
)

logger = logging.getLogger(__name__)


def find_shards(shards_dir: Path, dataset_name: str) -> list[Path]:
    """Find all downloaded shard files for a dataset."""
    releases = sorted(
        [
            path
            for path in shards_dir.iterdir()
            if path.is_dir() and not path.name.startswith("_")
        ],
        reverse=True,
    )
    for release_dir in releases:
        dataset_dir = release_dir / dataset_name
        if dataset_dir.exists():
            shards = sorted(dataset_dir.glob("*.jsonl.gz"))
            if shards:
                return shards
    return []


def read_json_clause(shard_path: str, columns: dict[str, str]) -> str:
    """Build a read_json SQL clause for a single shard file."""
    col_spec = ", ".join(f"{key}: '{value}'" for key, value in columns.items())
    return (
        f"read_json('{shard_path}', format='newline_delimited', "
        f"ignore_errors=true, columns={{{col_spec}}})"
    )


def ingest_dataset(dataset_name: str, shards: list[Path], db_path: Path) -> None:
    """Ingest a dataset's shards into DuckDB one shard at a time."""
    import duckdb

    conn = duckdb.connect(str(db_path))
    conn.execute("SET memory_limit='32GB'")
    conn.execute("SET threads=4")
    conn.execute("SET preserve_insertion_order=false")
    conn.execute(f"SET temp_directory='{db_path.parent / 'tmp'}'")

    for statement in CREATE_TABLES_SQL.split(";"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)

    logger.info(
        "Ingesting '%s' from %d shards (one at a time)",
        dataset_name,
        len(shards),
    )

    spec = DATASET_SPECS.get(dataset_name)
    if spec is None:
        logger.warning("No ingestion handler for dataset '%s'", dataset_name)
        conn.close()
        return

    for table_name in spec.reset_tables or (spec.table_name,):
        conn.execute(f"DELETE FROM {table_name}")

    t0 = time.monotonic()

    for index, shard in enumerate(shards, 1):
        shard_path = str(shard)
        for statement in spec.build_statements(shard_path, read_json_clause):
            conn.execute(statement)

        elapsed = time.monotonic() - t0
        logger.info(
            "  [%d/%d] %s (%.0fs elapsed)", index, len(shards), shard.name, elapsed
        )

    try:
        count = conn.execute(f"SELECT count(*) FROM {spec.table_name}").fetchone()[0]
    except Exception:
        count = "?"

    elapsed = time.monotonic() - t0
    logger.info("Ingested '%s': %s rows in %.1fs", dataset_name, count, elapsed)
    conn.execute(
        "INSERT OR REPLACE INTO _meta VALUES (?, ?)",
        [
            f"ingested_{spec.name}",
            json.dumps(
                {
                    "count": count if isinstance(count, int) else 0,
                    "elapsed_seconds": round(elapsed, 1),
                    "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            ),
        ],
    )
    conn.close()


def _sort_table(
    conn,
    table_name: str,
    sort_cols: str,
    is_copy: bool,
    source_table: str | None,
    t0: float,
) -> None:
    src = source_table if is_copy else table_name
    if is_copy:
        logger.info(
            "  Creating sorted copy %s (from %s, ORDER BY %s)...",
            table_name,
            src,
            sort_cols,
        )
        conn.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT * FROM {src} ORDER BY {sort_cols}
        """
        )
    else:
        logger.info("  Sorting %s by %s...", table_name, sort_cols)
        conn.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT * FROM {table_name} ORDER BY {sort_cols}
        """
        )
    elapsed = time.monotonic() - t0
    logger.info("  Done: %s (%.0fs elapsed)", table_name, elapsed)


def build_indexes(db_path: Path) -> None:
    """Optimize all tables for fast lookups via sorting plus zone maps."""
    import duckdb

    logger.info("Optimizing tables (sorting for zone-map lookups)...")
    conn = duckdb.connect(str(db_path))
    conn.execute("SET memory_limit='8GB'")
    conn.execute("SET threads=1")
    conn.execute("SET preserve_insertion_order=false")
    conn.execute(f"SET temp_directory='{db_path.parent / 'tmp'}'")
    t0 = time.monotonic()

    existing = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    for optimization in SORT_OPTIMIZATIONS:
        src = (
            optimization.source_table
            if optimization.is_copy
            else optimization.table_name
        )
        if src not in existing:
            logger.info(
                "  Skipping %s: source table %s not found",
                optimization.table_name,
                src,
            )
            continue
        if optimization.is_copy and optimization.table_name in existing:
            logger.info("  %s already exists, skipping", optimization.table_name)
            continue

        try:
            row = conn.execute(f"SELECT count(*) FROM {src}").fetchone()
            if not row or row[0] == 0:
                logger.info(
                    "  Skipping %s: source table %s is empty",
                    optimization.table_name,
                    src,
                )
                continue
        except Exception:
            continue

        _sort_table(
            conn,
            optimization.table_name,
            optimization.sort_cols,
            optimization.is_copy,
            optimization.source_table,
            t0,
        )

    elapsed = time.monotonic() - t0
    logger.info("All optimizations done in %.0fs", elapsed)
    conn.close()


def get_status(db_path: Path, shards_dir: Path) -> dict:
    """Get current pipeline status."""
    status = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "db_size_gb": round(db_path.stat().st_size / 1024**3, 2)
        if db_path.exists()
        else 0,
        "shards_path": str(shards_dir),
        "shards_exist": shards_dir.exists(),
        "datasets": {},
    }

    if db_path.exists():
        import duckdb

        conn = duckdb.connect(str(db_path), read_only=True)
        tables = conn.execute("SHOW TABLES").fetchall()
        for (table_name,) in tables:
            if table_name.startswith("_"):
                continue
            try:
                count = conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
                status["datasets"][table_name] = count
            except Exception:
                status["datasets"][table_name] = "error"
        conn.close()

    if shards_dir.exists():
        status["releases"] = sorted(
            [path.name for path in shards_dir.iterdir() if path.is_dir()],
            reverse=True,
        )

    return status
