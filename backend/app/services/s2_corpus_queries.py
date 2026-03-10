"""
DuckDB query specifications for the local Semantic Scholar corpus.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DuckDBQuerySpec:
    """Reusable query specification with optional fallback SQL."""

    sql: str
    fallback_sql: str | None = None
    prioritized_limit: bool = False
    expand_placeholders: bool = False

    def render(
        self,
        *,
        use_fallback: bool = False,
        value_count: int | None = None,
        limit: int | None = None,
    ) -> str:
        statement = self.fallback_sql if use_fallback and self.fallback_sql else self.sql
        if self.expand_placeholders:
            if value_count is None or value_count < 1:
                raise ValueError("value_count must be provided for placeholder queries")
            placeholders = ",".join("?" for _ in range(value_count))
            statement = statement.format(placeholders=placeholders)
        if self.prioritized_limit and limit is not None:
            statement += " ORDER BY isinfluential DESC LIMIT ?"
        return statement

    def bind(self, params: Sequence[object], *, limit: int | None = None) -> list[object]:
        bound = list(params)
        if self.prioritized_limit and limit is not None:
            bound.append(int(limit))
        return bound


SHA_TO_CORPUS_ID_QUERY = DuckDBQuerySpec(
    "SELECT corpusid FROM paper_ids WHERE sha = ? AND is_primary = true LIMIT 1"
)

CORPUS_ID_TO_SHA_QUERY = DuckDBQuerySpec(
    "SELECT sha FROM paper_ids_by_corpus WHERE corpusid = ? AND is_primary = true LIMIT 1",
    fallback_sql=(
        "SELECT sha FROM paper_ids WHERE corpusid = ? "
        "AND is_primary = true LIMIT 1"
    ),
)

BATCH_CORPUS_ID_TO_SHA_QUERY = DuckDBQuerySpec(
    "SELECT corpusid, sha FROM paper_ids_by_corpus "
    "WHERE corpusid IN ({placeholders}) AND is_primary = true",
    fallback_sql=(
        "SELECT corpusid, sha FROM paper_ids "
        "WHERE corpusid IN ({placeholders}) AND is_primary = true"
    ),
    expand_placeholders=True,
)

PAPER_BY_CORPUS_ID_QUERY = DuckDBQuerySpec(
    """
    SELECT title, year, venue, citationcount, referencecount,
           influentialcitationcount, isopenaccess, publicationdate
    FROM papers
    WHERE corpusid = ?
    """
)

ABSTRACT_BY_CORPUS_ID_QUERY = DuckDBQuerySpec(
    "SELECT abstract FROM abstracts WHERE corpusid = ?"
)

TLDR_BY_CORPUS_ID_QUERY = DuckDBQuerySpec(
    "SELECT text FROM tldrs WHERE corpusid = ?"
)

AUTHORS_BY_CORPUS_ID_QUERY = DuckDBQuerySpec(
    "SELECT authorid, name FROM paper_authors WHERE corpusid = ? ORDER BY position"
)

REFERENCES_BY_CITING_QUERY = DuckDBQuerySpec(
    "SELECT citedcorpusid, isinfluential FROM citations WHERE citingcorpusid = ?",
    prioritized_limit=True,
)

CITATIONS_BY_CITED_QUERY = DuckDBQuerySpec(
    "SELECT citingcorpusid, isinfluential FROM citations_by_cited WHERE citedcorpusid = ?",
    fallback_sql=(
        "SELECT citingcorpusid, isinfluential FROM citations "
        "WHERE citedcorpusid = ?"
    ),
    prioritized_limit=True,
)

RESOLVE_EXTERNAL_ID_QUERY = DuckDBQuerySpec(
    """
    SELECT pi.sha
    FROM paper_external_ids ei
    JOIN paper_ids pi ON ei.corpusid = pi.corpusid AND pi.is_primary = true
    WHERE ei.source = ? AND ei.id = ?
    LIMIT 1
    """
)

REFERENCE_IDS_QUERY = DuckDBQuerySpec(
    """
    SELECT pi.sha
    FROM citations c
    JOIN paper_ids pi ON c.citedcorpusid = pi.corpusid AND pi.is_primary = true
    WHERE c.citingcorpusid = ?
    """
)
