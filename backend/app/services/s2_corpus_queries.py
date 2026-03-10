"""
DuckDB query specifications for local S2 corpus access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DuckQuery:
    """A query with an optional fallback SQL variant."""

    sql: str
    params: tuple[Any, ...] = ()
    fallback_sql: str | None = None

    def fetchone(self, conn):
        try:
            return conn.execute(self.sql, list(self.params)).fetchone()
        except Exception:
            if self.fallback_sql is None:
                raise
            return conn.execute(self.fallback_sql, list(self.params)).fetchone()

    def fetchall(self, conn):
        try:
            return conn.execute(self.sql, list(self.params)).fetchall()
        except Exception:
            if self.fallback_sql is None:
                raise
            return conn.execute(self.fallback_sql, list(self.params)).fetchall()


def primary_corpus_id_query(s2_id: str) -> DuckQuery:
    return DuckQuery(
        sql=(
            "SELECT corpusid FROM paper_ids "
            "WHERE sha = ? AND is_primary = true LIMIT 1"
        ),
        params=(s2_id,),
    )


def primary_sha_query(corpus_id: int) -> DuckQuery:
    return DuckQuery(
        sql=(
            "SELECT sha FROM paper_ids_by_corpus "
            "WHERE corpusid = ? AND is_primary = true LIMIT 1"
        ),
        params=(corpus_id,),
        fallback_sql=(
            "SELECT sha FROM paper_ids "
            "WHERE corpusid = ? AND is_primary = true LIMIT 1"
        ),
    )


def batch_primary_sha_query(corpus_ids: list[int]) -> DuckQuery | None:
    if not corpus_ids:
        return None
    placeholders = ",".join("?" for _ in corpus_ids)
    return DuckQuery(
        sql=(
            "SELECT corpusid, sha FROM paper_ids_by_corpus "
            f"WHERE corpusid IN ({placeholders}) AND is_primary = true"
        ),
        params=tuple(corpus_ids),
        fallback_sql=(
            "SELECT corpusid, sha FROM paper_ids "
            f"WHERE corpusid IN ({placeholders}) AND is_primary = true"
        ),
    )


def paper_row_query(corpus_id: int) -> DuckQuery:
    return DuckQuery(
        sql=(
            "SELECT title, year, venue, citationcount, referencecount, "
            "influentialcitationcount, isopenaccess, publicationdate "
            "FROM papers WHERE corpusid = ?"
        ),
        params=(corpus_id,),
    )


def abstract_row_query(corpus_id: int) -> DuckQuery:
    return DuckQuery(
        sql="SELECT abstract FROM abstracts WHERE corpusid = ?",
        params=(corpus_id,),
    )


def tldr_row_query(corpus_id: int) -> DuckQuery:
    return DuckQuery(
        sql="SELECT text FROM tldrs WHERE corpusid = ?",
        params=(corpus_id,),
    )


def author_rows_query(corpus_id: int) -> DuckQuery:
    return DuckQuery(
        sql=(
            "SELECT authorid, name FROM paper_authors "
            "WHERE corpusid = ? ORDER BY position"
        ),
        params=(corpus_id,),
    )


def references_query(corpus_id: int, *, limit: int | None = None) -> DuckQuery:
    sql = "SELECT citedcorpusid, isinfluential FROM citations WHERE citingcorpusid = ?"
    if limit is not None:
        sql += f" ORDER BY isinfluential DESC LIMIT {int(limit)}"
    return DuckQuery(sql=sql, params=(corpus_id,))


def citations_query(corpus_id: int, *, limit: int | None = None) -> DuckQuery:
    sql = (
        "SELECT citingcorpusid, isinfluential "
        "FROM citations_by_cited WHERE citedcorpusid = ?"
    )
    fallback_sql = (
        "SELECT citingcorpusid, isinfluential "
        "FROM citations WHERE citedcorpusid = ?"
    )
    if limit is not None:
        suffix = f" ORDER BY isinfluential DESC LIMIT {int(limit)}"
        sql += suffix
        fallback_sql += suffix
    return DuckQuery(sql=sql, params=(corpus_id,), fallback_sql=fallback_sql)


def external_id_query(id_type: str, identifier: str) -> DuckQuery:
    return DuckQuery(
        sql=(
            "SELECT pi.sha FROM paper_external_ids ei "
            "JOIN paper_ids pi ON ei.corpusid = pi.corpusid AND pi.is_primary = true "
            "WHERE ei.source = ? AND ei.id = ? LIMIT 1"
        ),
        params=(id_type, identifier),
    )


def reference_ids_query(corpus_id: int) -> DuckQuery:
    return DuckQuery(
        sql=(
            "SELECT pi.sha "
            "FROM citations c "
            "JOIN paper_ids pi ON c.citedcorpusid = pi.corpusid AND pi.is_primary = true "
            "WHERE c.citingcorpusid = ?"
        ),
        params=(corpus_id,),
    )
