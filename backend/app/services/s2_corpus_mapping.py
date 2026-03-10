"""
Compatibility mapping helpers for S2 corpus record conversion.
"""

from __future__ import annotations

from typing import Any

from app.services.s2_corpus_mappers import CorpusRowMapper
from app.services.s2_protocol import EdgeRecord, PaperRecord


def paper_record_from_row(
    row: tuple,
    *,
    corpus_id: int,
    s2_id: str | None,
) -> PaperRecord:
    return CorpusRowMapper.paper_from_row(row, corpus_id=corpus_id, s2_id=s2_id)


def enrich_paper_record(
    base: PaperRecord,
    *,
    abstract_row: tuple | None,
    tldr_row: tuple | None,
    author_rows: list[tuple],
) -> PaperRecord:
    return CorpusRowMapper.enrich_paper(
        base,
        abstract_row=abstract_row,
        tldr_row=tldr_row,
        author_rows=author_rows,
    )


def reference_edges_from_rows(
    rows: list[tuple],
    *,
    citing_corpus_id: int,
    citing_s2_id: str,
    sha_map: dict[int, str],
) -> list[EdgeRecord]:
    return CorpusRowMapper.reference_edges(
        rows,
        citing_corpus_id=citing_corpus_id,
        citing_s2_id=citing_s2_id,
        sha_map=sha_map,
    )


def citation_edges_from_rows(
    rows: list[tuple],
    *,
    cited_corpus_id: int,
    cited_s2_id: str,
    sha_map: dict[int, str],
) -> list[EdgeRecord]:
    return CorpusRowMapper.citation_edges(
        rows,
        cited_corpus_id=cited_corpus_id,
        cited_s2_id=cited_s2_id,
        sha_map=sha_map,
    )


def api_dict_to_paper(data: dict[str, Any]) -> PaperRecord:
    return CorpusRowMapper.api_paper(data)
