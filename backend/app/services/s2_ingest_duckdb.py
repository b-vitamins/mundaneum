"""
DuckDB ingestion and optimization helpers for S2 datasets.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


CREATE_TABLES_SQL = """
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

SORT_OPTIMIZATIONS: list[tuple[str, str, bool, str | None]] = [
    ("citations", "citingcorpusid", False, None),
    ("citations_by_cited", "citedcorpusid", True, "citations"),
    ("paper_ids", "sha", False, None),
    ("paper_ids_by_corpus", "corpusid", True, "paper_ids"),
    ("paper_authors", "corpusid, position", False, None),
    ("paper_external_ids", "source, id", False, None),
]

DATASET_SCHEMAS: dict[str, dict[str, str]] = {
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

INSERT_TEMPLATES: dict[str, list[str]] = {
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

PAPERS_AUTHORS_SCHEMA = {"corpusid": "INTEGER", "authors": "JSON[]"}
PAPERS_EXTIDS_SCHEMA = {"corpusid": "INTEGER", "externalids": "JSON"}


def find_shards(shards_dir: Path, dataset_name: str) -> list[Path]:
    """Find all downloaded shard files for a dataset."""
    releases = sorted(
        [path for path in shards_dir.iterdir() if path.is_dir() and not path.name.startswith("_")],
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

    if dataset_name not in INSERT_TEMPLATES:
        logger.warning("No ingestion handler for dataset '%s'", dataset_name)
        conn.close()
        return

    schema = DATASET_SCHEMAS[dataset_name]
    table_name = dataset_name.replace("-", "_")
    conn.execute(f"DELETE FROM {table_name}")
    if dataset_name == "papers":
        conn.execute("DELETE FROM paper_authors")
        conn.execute("DELETE FROM paper_external_ids")

    t0 = time.monotonic()
    templates = INSERT_TEMPLATES[dataset_name]

    for index, shard in enumerate(shards, 1):
        shard_path = str(shard)
        src = read_json_clause(shard_path, schema)

        for template in templates:
            conn.execute(template.format(src=src))

        if dataset_name == "papers":
            author_src = read_json_clause(shard_path, PAPERS_AUTHORS_SCHEMA)
            conn.execute(f"""
                INSERT INTO paper_authors
                SELECT corpusid,
                       json_extract_string(author, '$.authorId'),
                       json_extract_string(author, '$.name'),
                       (row_number() OVER (PARTITION BY corpusid)) - 1
                FROM (
                    SELECT corpusid, unnest(authors) AS author
                    FROM {author_src}
                    WHERE authors IS NOT NULL
                )
            """)

            extid_src = read_json_clause(shard_path, PAPERS_EXTIDS_SCHEMA)
            conn.execute(f"""
                INSERT INTO paper_external_ids
                SELECT corpusid, key, value
                FROM (
                    SELECT corpusid,
                           unnest(map_keys(CAST(externalids AS MAP(VARCHAR, VARCHAR)))) AS key,
                           unnest(map_values(CAST(externalids AS MAP(VARCHAR, VARCHAR)))) AS value
                    FROM {extid_src}
                    WHERE externalids IS NOT NULL
                )
                WHERE value IS NOT NULL AND value != ''
            """)

        elapsed = time.monotonic() - t0
        logger.info("  [%d/%d] %s (%.0fs elapsed)", index, len(shards), shard.name, elapsed)

    try:
        count = conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
    except Exception:
        count = "?"

    elapsed = time.monotonic() - t0
    logger.info("Ingested '%s': %s rows in %.1fs", dataset_name, count, elapsed)
    conn.execute(
        "INSERT OR REPLACE INTO _meta VALUES (?, ?)",
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
) -> None:
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
    for table_name, sort_cols, is_copy, source_table in SORT_OPTIMIZATIONS:
        src = source_table if is_copy else table_name
        if src not in existing:
            logger.info("  Skipping %s: source table %s not found", table_name, src)
            continue
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
    """Get current pipeline status."""
    status = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "db_size_gb": round(db_path.stat().st_size / 1024**3, 2) if db_path.exists() else 0,
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
