"""
Helper tests for S2 corpus query, mapping, and registry modules.
"""

from __future__ import annotations

import pytest

from app.services.s2_corpus_mapping import (
    api_dict_to_paper,
    citation_edges_from_rows,
    paper_record_from_row,
    reference_edges_from_rows,
)
from app.services.s2_corpus_queries import primary_sha_query
from app.services.s2_source_registry import SourceRegistry


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FallbackConn:
    def __init__(self):
        self.calls: list[str] = []

    def execute(self, sql, params):
        self.calls.append(sql)
        if "paper_ids_by_corpus" in sql:
            raise RuntimeError("optimized table missing")
        assert params == [42]
        return _FakeCursor([("sha-42",)])


class _NoneSource:
    async def get_paper(self, _s2_id):
        return None


class _EmptySource:
    async def get_paper(self, _s2_id):
        return []


class _ValueSource:
    async def get_paper(self, _s2_id):
        return ["paper"]


def test_primary_sha_query_uses_fallback_sql():
    """Fallback SQL should be exercised when the optimized table is absent."""
    conn = _FallbackConn()
    row = primary_sha_query(42).fetchone(conn)
    assert row == ("sha-42",)
    assert len(conn.calls) == 2


def test_api_dict_to_paper_normalizes_nested_fields():
    """Live API mapping should flatten nested author, TLDR, and field data."""
    record = api_dict_to_paper(
        {
            "paperId": "paper-1",
            "title": "Flexible Systems",
            "authors": [{"authorId": "a1", "name": "Ada"}],
            "tldr": {"text": "A compact summary."},
            "openAccessPdf": {"url": "https://example.test/paper.pdf"},
            "fieldsOfStudy": [{"category": "Computer Science"}],
            "publicationTypes": ["JournalArticle"],
            "externalIds": {"DOI": "10.1/example"},
        }
    )
    assert record.s2_id == "paper-1"
    assert record.authors == [{"authorId": "a1", "name": "Ada"}]
    assert record.tldr == "A compact summary."
    assert record.open_access_pdf_url == "https://example.test/paper.pdf"
    assert record.fields_of_study == ["Computer Science"]


def test_row_mappers_build_edge_records():
    """Reference and citation row mappers should preserve graph direction."""
    references = reference_edges_from_rows(
        [(2, True), (3, False)],
        citing_corpus_id=1,
        citing_s2_id="source",
        sha_map={2: "target-2", 3: "target-3"},
    )
    citations = citation_edges_from_rows(
        [(2, True)],
        cited_corpus_id=1,
        cited_s2_id="target",
        sha_map={2: "source-2"},
    )
    assert references[0].citing_corpus_id == 1
    assert references[0].cited_s2_id == "target-2"
    assert citations[0].citing_s2_id == "source-2"
    assert citations[0].cited_s2_id == "target"


def test_paper_record_from_row_preserves_corpus_identity():
    """Base paper-row mapping should keep corpus and S2 identifiers aligned."""
    record = paper_record_from_row(
        ("Flexible Systems", 1985, "MIT", 9, 4, 2, True, None),
        corpus_id=7,
        s2_id="paper-7",
    )
    assert record.corpus_id == 7
    assert record.s2_id == "paper-7"
    assert record.citation_count == 9


@pytest.mark.asyncio
async def test_source_registry_stops_on_first_non_none_result():
    """An empty list is a real result and should stop the chain."""
    registry = SourceRegistry([_NoneSource(), _EmptySource(), _ValueSource()])
    result = await registry.first_result(lambda source: source.get_paper("paper"))
    assert result == []
