"""
Dataset specifications for the S2 DuckDB ingest pipeline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

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

PAPERS_AUTHORS_SCHEMA = {"corpusid": "INTEGER", "authors": "JSON[]"}
PAPERS_EXTIDS_SCHEMA = {"corpusid": "INTEGER", "externalids": "JSON"}


ReadJsonBuilder = Callable[[str, dict[str, str]], str]


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """One declarative dataset ingest specification."""

    name: str
    table_name: str
    schema: dict[str, str]
    insert_templates: tuple[str, ...]
    reset_tables: tuple[str, ...] = field(default_factory=tuple)
    extra_statements: Callable[[str, ReadJsonBuilder], list[str]] | None = None

    def build_statements(
        self,
        shard_path: str,
        read_json_clause: ReadJsonBuilder,
    ) -> list[str]:
        src = read_json_clause(shard_path, self.schema)
        statements = [template.format(src=src) for template in self.insert_templates]
        if self.extra_statements is not None:
            statements.extend(self.extra_statements(shard_path, read_json_clause))
        return statements


@dataclass(frozen=True, slots=True)
class SortOptimization:
    table_name: str
    sort_cols: str
    is_copy: bool = False
    source_table: str | None = None


def _paper_extra_statements(
    shard_path: str,
    read_json_clause: ReadJsonBuilder,
) -> list[str]:
    author_src = read_json_clause(shard_path, PAPERS_AUTHORS_SCHEMA)
    extid_src = read_json_clause(shard_path, PAPERS_EXTIDS_SCHEMA)
    return [
        f"""
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
        """,
        f"""
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
        """,
    ]


DATASET_SPECS: dict[str, DatasetSpec] = {
    "papers": DatasetSpec(
        name="papers",
        table_name="papers",
        schema={
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
        insert_templates=(
            """INSERT INTO papers
               SELECT corpusid, title, year, venue, citationcount, referencecount,
                      influentialcitationcount, isopenaccess, publicationdate, publicationvenueid
               FROM {src}""",
        ),
        reset_tables=("papers", "paper_authors", "paper_external_ids"),
        extra_statements=_paper_extra_statements,
    ),
    "citations": DatasetSpec(
        name="citations",
        table_name="citations",
        schema={
            "citingcorpusid": "INTEGER",
            "citedcorpusid": "INTEGER",
            "isinfluential": "BOOLEAN",
        },
        insert_templates=(
            """INSERT INTO citations SELECT citingcorpusid, citedcorpusid, isinfluential
               FROM {src} WHERE citingcorpusid IS NOT NULL AND citedcorpusid IS NOT NULL""",
        ),
    ),
    "authors": DatasetSpec(
        name="authors",
        table_name="authors",
        schema={
            "authorid": "VARCHAR",
            "name": "VARCHAR",
            "papercount": "INTEGER",
            "citationcount": "INTEGER",
            "hindex": "INTEGER",
        },
        insert_templates=(
            "INSERT INTO authors SELECT authorid, name, papercount, citationcount, hindex FROM {src}",
        ),
    ),
    "abstracts": DatasetSpec(
        name="abstracts",
        table_name="abstracts",
        schema={"corpusid": "INTEGER", "abstract": "VARCHAR"},
        insert_templates=("INSERT INTO abstracts SELECT corpusid, abstract FROM {src}",),
    ),
    "tldrs": DatasetSpec(
        name="tldrs",
        table_name="tldrs",
        schema={"corpusid": "INTEGER", "text": "VARCHAR"},
        insert_templates=("INSERT INTO tldrs SELECT corpusid, text FROM {src}",),
    ),
    "paper-ids": DatasetSpec(
        name="paper-ids",
        table_name="paper_ids",
        schema={"sha": "VARCHAR", "corpusid": "INTEGER", '"primary"': "BOOLEAN"},
        insert_templates=(
            'INSERT INTO paper_ids SELECT sha, corpusid, "primary" FROM {src}',
        ),
    ),
    "publication-venues": DatasetSpec(
        name="publication-venues",
        table_name="publication_venues",
        schema={
            "id": "VARCHAR",
            "name": "VARCHAR",
            "type": "VARCHAR",
            "issn": "VARCHAR",
        },
        insert_templates=(
            "INSERT INTO publication_venues SELECT id, name, type, issn FROM {src}",
        ),
    ),
}


SORT_OPTIMIZATIONS: tuple[SortOptimization, ...] = (
    SortOptimization("citations", "citingcorpusid"),
    SortOptimization("citations_by_cited", "citedcorpusid", True, "citations"),
    SortOptimization("paper_ids", "sha"),
    SortOptimization("paper_ids_by_corpus", "corpusid", True, "paper_ids"),
    SortOptimization("paper_authors", "corpusid, position"),
    SortOptimization("paper_external_ids", "source, id"),
)
