"""
S2 dataset ingestion pipeline — download, ingest, update.

Downloads S2 Academic Graph dataset shards to local storage,
then ingests them into a DuckDB database for fast querying.

Usage:
    python -m app.services.s2_ingest download --datasets papers,citations
    python -m app.services.s2_ingest ingest
    python -m app.services.s2_ingest status
    python -m app.services.s2_ingest update --from 2026-02-10 --to 2026-02-17
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

S2_DATASETS_API = "https://api.semanticscholar.org/datasets/v1"

# Core datasets we ingest (ordered by priority)
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


def _load_settings():
    """Load settings from .env / config. Works outside of FastAPI context."""
    try:
        from app.config import settings

        return {
            "api_key": settings.s2_api_key,
            "shards_path": settings.s2_shards_path,
            "corpus_path": settings.s2_corpus_path,
        }
    except Exception:
        # Fallback for standalone usage
        from dotenv import dotenv_values

        env = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
        return {
            "api_key": env.get("S2_API_KEY"),
            "shards_path": env.get("S2_SHARDS_PATH", "/data/s2/shards"),
            "corpus_path": env.get("S2_CORPUS_PATH", "/data/s2/corpus.duckdb"),
        }


# ──────────────────────────────────────────────────────────
# Download
# ──────────────────────────────────────────────────────────


def _api_get(
    url: str, api_key: str | None = None, max_retries: int = 5
) -> httpx.Response:
    """GET with retry + exponential backoff for 429s."""
    headers = {"x-api-key": api_key} if api_key else {}
    for attempt in range(max_retries):
        resp = httpx.get(url, headers=headers, timeout=30)
        if resp.status_code == 429:
            wait = 2.0 * (2**attempt)
            logger.warning(
                "S2 Datasets API 429, retry in %.1fs (%s)", wait, url.split("/")[-1]
            )
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()  # final attempt — let it raise
    return resp


def get_latest_release(api_key: str | None = None) -> str:
    """Get the latest release date from the S2 Datasets API."""
    resp = _api_get(f"{S2_DATASETS_API}/release/latest", api_key)
    return resp.json()["release_id"]


def get_download_links(
    dataset_name: str,
    release_id: str,
    api_key: str,
) -> list[str]:
    """Get pre-signed S3 download URLs for a dataset's shards."""
    resp = _api_get(
        f"{S2_DATASETS_API}/release/{release_id}/dataset/{dataset_name}",
        api_key,
    )
    return resp.json().get("files", [])


def download_shard(url: str, dest: Path, max_retries: int = 3) -> bool | str:
    """Download a single shard to dest.

    Returns:
        True     — downloaded successfully
        False    — skipped (already exists) or permanent failure
        'expired' — pre-signed URL expired (400), caller should refresh

    Retries on network errors with exponential backoff.
    Uses atomic writes (.tmp → rename) to prevent corrupt files.
    """
    if dest.exists() and dest.stat().st_size > 0:
        logger.info("  ✓ Already exists: %s", dest.name)
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")

    for attempt in range(max_retries):
        # Clean up any stale .tmp from previous failed attempt
        if tmp.exists():
            tmp.unlink()

        if attempt > 0:
            wait = 5.0 * (2 ** (attempt - 1))
            logger.warning(
                "  ↻ Retry %d/%d for %s in %.0fs",
                attempt + 1,
                max_retries,
                dest.name,
                wait,
            )
            time.sleep(wait)

        logger.info("  ↓ Downloading: %s", dest.name)
        t0 = time.monotonic()

        try:
            with httpx.stream(
                "GET",
                url,
                timeout=httpx.Timeout(connect=30, read=600, write=30, pool=30),
                follow_redirects=True,
            ) as resp:
                if resp.status_code == 400:
                    logger.warning("  ⚠ URL expired (400) for %s", dest.name)
                    return "expired"
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(tmp, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8 * 1024 * 1024):  # 8 MB
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded / total * 100
                            elapsed_so_far = time.monotonic() - t0
                            rate = (
                                downloaded / elapsed_so_far / 1024 / 1024
                                if elapsed_so_far > 0
                                else 0
                            )
                            print(
                                f"\r    {pct:.1f}% ({rate:.1f} MB/s)",
                                end="",
                                flush=True,
                            )

            print()  # newline after progress

            # Verify we got the full file
            if total > 0 and downloaded < total:
                logger.warning(
                    "  ⚠ Incomplete: got %d/%d bytes for %s",
                    downloaded,
                    total,
                    dest.name,
                )
                continue  # retry

            tmp.rename(dest)
            elapsed = time.monotonic() - t0
            size_mb = dest.stat().st_size / 1024 / 1024
            logger.info(
                "  ✓ %s: %.1f MB in %.1fs (%.1f MB/s)",
                dest.name,
                size_mb,
                elapsed,
                size_mb / elapsed if elapsed > 0 else 0,
            )
            return True

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.HTTPStatusError,
            OSError,
        ) as e:
            print()  # newline after partial progress
            logger.warning(
                "  ✗ Failed %s (attempt %d/%d): %s",
                dest.name,
                attempt + 1,
                max_retries,
                e,
            )
            continue

    # All retries exhausted
    logger.error("  ✗ Gave up on %s after %d attempts", dest.name, max_retries)
    if tmp.exists():
        tmp.unlink()
    return False


# Pre-signed URLs expire after ~1 hour; refresh well before that
_URL_REFRESH_INTERVAL = 30 * 60  # 30 minutes


def download_dataset(
    dataset_name: str,
    shards_dir: Path,
    api_key: str,
    release_id: str | None = None,
) -> Path:
    """Download all shards for a dataset. Returns the dataset directory.

    Automatically re-fetches pre-signed S3 URLs when they expire (400)
    or when they are older than 30 minutes.
    """
    if not release_id:
        release_id = get_latest_release(api_key)

    logger.info("Downloading '%s' from release %s", dataset_name, release_id)

    urls = get_download_links(dataset_name, release_id, api_key)
    urls_fetched_at = time.monotonic()
    if not urls:
        logger.error("No download links for dataset '%s'", dataset_name)
        raise RuntimeError(f"No download links for {dataset_name}")

    dataset_dir = shards_dir / release_id / dataset_name
    dataset_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    failed = 0

    for i in range(len(urls)):
        shard_name = f"{i:03d}.jsonl.gz"
        dest = dataset_dir / shard_name

        # Proactively refresh URLs before they expire
        if time.monotonic() - urls_fetched_at > _URL_REFRESH_INTERVAL:
            logger.info("  🔄 Refreshing download URLs (older than 30m)...")
            urls = get_download_links(dataset_name, release_id, api_key)
            urls_fetched_at = time.monotonic()

        result = download_shard(urls[i], dest)

        if result == "expired":
            # URL expired — get fresh ones and retry this shard
            logger.info("  🔄 Refreshing download URLs (expired)...")
            urls = get_download_links(dataset_name, release_id, api_key)
            urls_fetched_at = time.monotonic()
            result = download_shard(urls[i], dest)

        if result is True:
            downloaded += 1
        elif result is False:
            pass  # skipped (already existed)
        else:
            failed += 1

    logger.info(
        "Dataset '%s': %d downloaded, %d failed, %d total shards",
        dataset_name,
        downloaded,
        failed,
        len(urls),
    )

    # Write metadata
    meta_path = dataset_dir / "_meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "dataset": dataset_name,
                "release_id": release_id,
                "shard_count": len(urls),
                "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            indent=2,
        )
    )

    return dataset_dir


# ──────────────────────────────────────────────────────────
# Ingest into DuckDB
# ──────────────────────────────────────────────────────────

# SQL to create tables
_CREATE_TABLES_SQL = """
-- Papers (200M rows)
CREATE TABLE IF NOT EXISTS papers (
    corpusid       INTEGER PRIMARY KEY,
    title          VARCHAR,
    year           SMALLINT,
    venue          VARCHAR,
    citationcount  INTEGER DEFAULT 0,
    referencecount INTEGER DEFAULT 0,
    influentialcitationcount INTEGER DEFAULT 0,
    isopenaccess   BOOLEAN DEFAULT FALSE,
    publicationdate VARCHAR,
    publicationvenueid VARCHAR
);

-- Citations (2.4B rows)
CREATE TABLE IF NOT EXISTS citations (
    citingcorpusid INTEGER,
    citedcorpusid  INTEGER,
    isinfluential  BOOLEAN DEFAULT FALSE
);

-- Authors (75M rows)
CREATE TABLE IF NOT EXISTS authors (
    authorid      VARCHAR PRIMARY KEY,
    name          VARCHAR,
    papercount    INTEGER DEFAULT 0,
    citationcount INTEGER DEFAULT 0,
    hindex        INTEGER DEFAULT 0
);

-- Abstracts (100M rows)
CREATE TABLE IF NOT EXISTS abstracts (
    corpusid INTEGER PRIMARY KEY,
    abstract VARCHAR
);

-- TLDRs (58M rows)
CREATE TABLE IF NOT EXISTS tldrs (
    corpusid INTEGER,
    text     VARCHAR
);

-- Paper ID mappings (450M rows)
CREATE TABLE IF NOT EXISTS paper_ids (
    sha        VARCHAR NOT NULL,
    corpusid   INTEGER NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE
);

-- Publication venues
CREATE TABLE IF NOT EXISTS publication_venues (
    id   VARCHAR PRIMARY KEY,
    name VARCHAR,
    type VARCHAR,
    issn VARCHAR
);

-- Paper external IDs (flattened from papers.externalids)
CREATE TABLE IF NOT EXISTS paper_external_ids (
    corpusid INTEGER NOT NULL,
    source   VARCHAR NOT NULL,
    id       VARCHAR NOT NULL
);

-- Paper authors (flattened from papers.authors)
CREATE TABLE IF NOT EXISTS paper_authors (
    corpusid INTEGER NOT NULL,
    authorid VARCHAR,
    name     VARCHAR,
    position SMALLINT
);

-- Pipeline metadata
CREATE TABLE IF NOT EXISTS _meta (
    key   VARCHAR PRIMARY KEY,
    value VARCHAR
);
"""

# No ART indexes — DuckDB ART index creation is in-memory only and cannot
# spill to disk.  On tables with >100M rows this exceeds 64GB RAM.
#
# Instead, we sort tables by their primary lookup key.  DuckDB stores
# min/max zone-map stats per row group (~120K rows).  On sorted data,
# point queries check these stats and skip 99.99% of row groups —
# giving index-equivalent speed with zero extra memory.
#
# Tables needing lookups on two keys get a reverse-sorted copy.

# (table_name, sort_columns, is_reverse_copy, source_table)
_SORT_OPTIMIZATIONS: list[tuple[str, str, bool, str | None]] = [
    # Citations: sorted both ways for reference + citation lookups
    ("citations", "citingcorpusid", False, None),
    ("citations_by_cited", "citedcorpusid", True, "citations"),
    # Paper IDs: sorted by sha (primary lookup), reverse by corpusid
    ("paper_ids", "sha", False, None),
    ("paper_ids_by_corpus", "corpusid", True, "paper_ids"),
    # Paper authors: sorted by corpusid (primary lookup)
    ("paper_authors", "corpusid, position", False, None),
    # Paper external IDs: sorted by (source, id) for resolve_id
    ("paper_external_ids", "source, id", False, None),
]


def _find_shards(shards_dir: Path, dataset_name: str) -> list[Path]:
    """Find all downloaded shard files for a dataset."""
    # Find latest release
    releases = sorted(
        [d for d in shards_dir.iterdir() if d.is_dir() and not d.name.startswith("_")],
        reverse=True,
    )
    for release_dir in releases:
        ds_dir = release_dir / dataset_name
        if ds_dir.exists():
            shards = sorted(ds_dir.glob("*.jsonl.gz"))
            if shards:
                return shards
    return []


def _read_json_clause(shard_path: str, columns: dict[str, str]) -> str:
    """Build a read_json SQL clause for a single shard file."""
    col_spec = ", ".join(f"{k}: '{v}'" for k, v in columns.items())
    return (
        f"read_json('{shard_path}', format='newline_delimited', "
        f"ignore_errors=true, columns={{{col_spec}}})"
    )


# Per-dataset column schemas for read_json
_DATASET_SCHEMAS: dict[str, dict[str, str]] = {
    "papers": {
        "corpusid": "INTEGER",
        "title": "VARCHAR",
        "year": "SMALLINT",
        "venue": "VARCHAR",
        "citationcount": "INTEGER",
        "referencecount": "INTEGER",
        "influentialcitationcount": "INTEGER",
        "isopenaccess": "BOOLEAN",
        "publicationdate": "VARCHAR",
        "publicationvenueid": "VARCHAR",
    },
    "citations": {
        "citingcorpusid": "INTEGER",
        "citedcorpusid": "INTEGER",
        "isinfluential": "BOOLEAN",
    },
    "authors": {
        "authorid": "VARCHAR",
        "name": "VARCHAR",
        "papercount": "INTEGER",
        "citationcount": "INTEGER",
        "hindex": "INTEGER",
    },
    "abstracts": {"corpusid": "INTEGER", "abstract": "VARCHAR"},
    "tldrs": {"corpusid": "INTEGER", "text": "VARCHAR"},
    "paper-ids": {"sha": "VARCHAR", "corpusid": "INTEGER", '"primary"': "BOOLEAN"},
    "publication-venues": {
        "id": "VARCHAR",
        "name": "VARCHAR",
        "type": "VARCHAR",
        "issn": "VARCHAR",
    },
}

# SQL templates: {src} will be replaced with the read_json clause for each shard
_INSERT_TEMPLATES: dict[str, list[str]] = {
    "papers": [
        """INSERT INTO papers
           SELECT corpusid, title, year, venue, citationcount, referencecount,
                  influentialcitationcount, isopenaccess, publicationdate, publicationvenueid
           FROM {src}""",
    ],
    "citations": [
        """INSERT INTO citations SELECT citingcorpusid, citedcorpusid, isinfluential
           FROM {src} WHERE citingcorpusid IS NOT NULL AND citedcorpusid IS NOT NULL""",
    ],
    "authors": [
        "INSERT INTO authors SELECT authorid, name, papercount, citationcount, hindex FROM {src}",
    ],
    "abstracts": [
        "INSERT INTO abstracts SELECT corpusid, abstract FROM {src}",
    ],
    "tldrs": [
        "INSERT INTO tldrs SELECT corpusid, text FROM {src}",
    ],
    "paper-ids": [
        'INSERT INTO paper_ids SELECT sha, corpusid, "primary" FROM {src}',
    ],
    "publication-venues": [
        "INSERT INTO publication_venues SELECT id, name, type, issn FROM {src}",
    ],
}

# Extra per-shard SQL that uses different column schemas (papers flatten)
_PAPERS_AUTHORS_SCHEMA = {"corpusid": "INTEGER", "authors": "JSON[]"}
_PAPERS_EXTIDS_SCHEMA = {"corpusid": "INTEGER", "externalids": "JSON"}


def ingest_dataset(
    dataset_name: str,
    shards: list[Path],
    db_path: Path,
):
    """Ingest a dataset's shards into DuckDB, one shard at a time.

    Processing shards individually keeps memory usage bounded and
    avoids the OOM kills that occur when globbing all files at once.
    """
    import duckdb

    conn = duckdb.connect(str(db_path))
    conn.execute("SET memory_limit='32GB'")
    conn.execute("SET threads=4")
    conn.execute("SET preserve_insertion_order=false")
    conn.execute(f"SET temp_directory='{db_path.parent / 'tmp'}'")

    # Ensure tables exist
    for stmt in _CREATE_TABLES_SQL.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)

    logger.info(
        "Ingesting '%s' from %d shards (one at a time)", dataset_name, len(shards)
    )

    if dataset_name not in _INSERT_TEMPLATES:
        logger.warning("No ingestion handler for dataset '%s'", dataset_name)
        conn.close()
        return

    schema = _DATASET_SCHEMAS[dataset_name]

    # Clear existing data
    table_name = dataset_name.replace("-", "_")
    conn.execute(f"DELETE FROM {table_name}")
    if dataset_name == "papers":
        conn.execute("DELETE FROM paper_authors")
        conn.execute("DELETE FROM paper_external_ids")

    t0 = time.monotonic()
    templates = _INSERT_TEMPLATES[dataset_name]

    for i, shard in enumerate(shards, 1):
        shard_path = str(shard)
        src = _read_json_clause(shard_path, schema)

        for tmpl in templates:
            conn.execute(tmpl.format(src=src))

        # Papers have extra flatten steps per shard
        if dataset_name == "papers":
            # Flatten authors
            author_src = _read_json_clause(shard_path, _PAPERS_AUTHORS_SCHEMA)
            conn.execute(f"""
                INSERT INTO paper_authors
                SELECT corpusid,
                       json_extract_string(author, '$.authorId'),
                       json_extract_string(author, '$.name'),
                       (row_number() OVER (PARTITION BY corpusid)) - 1
                FROM (
                    SELECT corpusid, unnest(authors) as author
                    FROM {author_src}
                    WHERE authors IS NOT NULL
                )
            """)

            # Flatten external IDs
            extid_src = _read_json_clause(shard_path, _PAPERS_EXTIDS_SCHEMA)
            conn.execute(f"""
                INSERT INTO paper_external_ids
                SELECT corpusid, key, value
                FROM (
                    SELECT corpusid,
                           unnest(map_keys(CAST(externalids AS MAP(VARCHAR, VARCHAR)))) as key,
                           unnest(map_values(CAST(externalids AS MAP(VARCHAR, VARCHAR)))) as value
                    FROM {extid_src}
                    WHERE externalids IS NOT NULL
                )
                WHERE value IS NOT NULL AND value != ''
            """)

        elapsed = time.monotonic() - t0
        logger.info("  [%d/%d] %s (%.0fs elapsed)", i, len(shards), shard.name, elapsed)

    # Record count
    try:
        count = conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
    except Exception:
        count = "?"

    elapsed = time.monotonic() - t0
    logger.info("Ingested '%s': %s rows in %.1fs", dataset_name, count, elapsed)

    # Update metadata
    conn.execute(
        """
        INSERT OR REPLACE INTO _meta VALUES (?, ?)
    """,
        [
            f"ingested_{dataset_name}",
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
):
    """Sort a table in-place or create a sorted copy."""
    src = source_table if is_copy else table_name
    if is_copy:
        logger.info(
            "  Creating sorted copy %s (from %s, ORDER BY %s)...",
            table_name,
            src,
            sort_cols,
        )
        conn.execute(f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT * FROM {src} ORDER BY {sort_cols}
        """)
    else:
        logger.info("  Sorting %s by %s...", table_name, sort_cols)
        conn.execute(f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT * FROM {table_name} ORDER BY {sort_cols}
        """)
    elapsed = time.monotonic() - t0
    logger.info("  Done: %s (%.0fs elapsed)", table_name, elapsed)


def build_indexes(db_path: Path):
    """Optimize all tables for fast lookups via sorting + zone maps.

    DuckDB ART indexes are in-memory only (cannot spill to disk),
    making them unusable for tables with >100M rows on a 64GB machine.

    Instead, we sort each table by its primary lookup key.  DuckDB's
    zone-map stats (min/max per row group) then let point queries skip
    99.99% of the data — equivalent to an index, zero extra RAM.

    ORDER BY *does* support spilling to disk via temp_directory.
    """
    import duckdb

    logger.info("Optimizing tables (sorting for zone-map lookups)...")
    conn = duckdb.connect(str(db_path))
    conn.execute("SET memory_limit='8GB'")
    conn.execute("SET threads=1")
    conn.execute("SET preserve_insertion_order=false")
    conn.execute(f"SET temp_directory='{db_path.parent / 'tmp'}'")
    t0 = time.monotonic()

    existing = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}

    for table_name, sort_cols, is_copy, source_table in _SORT_OPTIMIZATIONS:
        src = source_table if is_copy else table_name

        # Skip if source table doesn't exist or is empty
        if src not in existing:
            logger.info("  Skipping %s: source table %s not found", table_name, src)
            continue

        # Skip reverse copies that already exist (idempotent)
        if is_copy and table_name in existing:
            logger.info("  %s already exists, skipping", table_name)
            continue

        try:
            row = conn.execute(f"SELECT count(*) FROM {src}").fetchone()
            if not row or row[0] == 0:
                logger.info("  Skipping %s: source table %s is empty", table_name, src)
                continue
        except Exception:
            continue

        _sort_table(conn, table_name, sort_cols, is_copy, source_table, t0)

    elapsed = time.monotonic() - t0
    logger.info("All optimizations done in %.0fs", elapsed)
    conn.close()


def get_status(db_path: Path, shards_dir: Path) -> dict:
    """Get pipeline status."""
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
            [d.name for d in shards_dir.iterdir() if d.is_dir()],
            reverse=True,
        )

    return status


# ──────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="S2 Academic Graph dataset pipeline",
        prog="s2_ingest",
    )
    sub = parser.add_subparsers(dest="command")

    # download
    dl = sub.add_parser("download", help="Download dataset shards from S2")
    dl.add_argument(
        "--datasets",
        type=str,
        default=",".join(CORE_DATASETS),
        help="Comma-separated dataset names (default: core datasets)",
    )
    dl.add_argument(
        "--all",
        action="store_true",
        dest="all_datasets",
        help="Download ALL datasets (including embeddings + full-text)",
    )
    dl.add_argument("--release", type=str, help="Release date (default: latest)")

    # ingest
    ing = sub.add_parser("ingest", help="Ingest downloaded shards into DuckDB")
    ing.add_argument(
        "--datasets",
        type=str,
        default=",".join(CORE_DATASETS),
        help="Comma-separated dataset names to ingest",
    )
    ing.add_argument(
        "--all",
        action="store_true",
        dest="all_datasets",
        help="Ingest ALL downloaded datasets",
    )
    ing.add_argument("--no-index", action="store_true", help="Skip index building")

    # status
    sub.add_parser("status", help="Show pipeline status")

    args = parser.parse_args()
    cfg = _load_settings()

    shards_dir = Path(cfg["shards_path"])
    db_path = Path(cfg["corpus_path"])

    if args.command == "download":
        if not cfg["api_key"]:
            logger.error(
                "S2_API_KEY is required for downloading datasets. Set it in .env"
            )
            sys.exit(1)

        datasets = (
            ALL_DATASETS
            if args.all_datasets
            else [d.strip() for d in args.datasets.split(",")]
        )
        release = args.release

        for ds in datasets:
            try:
                download_dataset(ds, shards_dir, cfg["api_key"], release)
            except Exception as e:
                logger.error("Failed to download '%s': %s", ds, e)
                continue

    elif args.command == "ingest":
        db_path.parent.mkdir(parents=True, exist_ok=True)
        datasets = (
            ALL_DATASETS
            if args.all_datasets
            else [d.strip() for d in args.datasets.split(",")]
        )

        for ds in datasets:
            shards = _find_shards(shards_dir, ds)
            if not shards:
                logger.warning("No shards found for '%s' — download first", ds)
                continue
            try:
                ingest_dataset(ds, shards, db_path)
            except Exception as e:
                logger.error("Failed to ingest '%s': %s", ds, e)
                import traceback

                traceback.print_exc()
                continue

        if not args.no_index:
            build_indexes(db_path)

        logger.info("Done. DuckDB size: %.2f GB", db_path.stat().st_size / 1024**3)

    elif args.command == "status":
        status = get_status(db_path, shards_dir)
        print(json.dumps(status, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
