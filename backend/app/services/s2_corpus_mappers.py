"""
Row mappers for local-corpus and live S2 payloads.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.s2_protocol import EdgeRecord, PaperRecord


class CorpusRowMapper:
    """Pure mapping helpers for S2 corpus records."""

    @staticmethod
    def paper_from_row(
        row: Sequence[Any],
        *,
        corpus_id: int,
        s2_id: str | None,
    ) -> PaperRecord:
        return PaperRecord(
            corpus_id=corpus_id,
            s2_id=s2_id,
            title=row[0] or "",
            year=row[1],
            venue=row[2],
            citation_count=row[3] or 0,
            reference_count=row[4] or 0,
            influential_citation_count=row[5] or 0,
            is_open_access=bool(row[6]),
        )

    @staticmethod
    def enrich_paper(
        paper: PaperRecord,
        *,
        abstract_row: Sequence[Any] | None,
        tldr_row: Sequence[Any] | None,
        author_rows: Sequence[Sequence[Any]],
    ) -> PaperRecord:
        return PaperRecord(
            corpus_id=paper.corpus_id,
            s2_id=paper.s2_id,
            title=paper.title,
            year=paper.year,
            venue=paper.venue,
            authors=[{"authorId": row[0], "name": row[1]} for row in author_rows],
            abstract=abstract_row[0] if abstract_row else None,
            tldr=tldr_row[0] if tldr_row else None,
            citation_count=paper.citation_count,
            reference_count=paper.reference_count,
            influential_citation_count=paper.influential_citation_count,
            is_open_access=paper.is_open_access,
            open_access_pdf_url=paper.open_access_pdf_url,
            fields_of_study=list(paper.fields_of_study),
            publication_types=list(paper.publication_types),
            external_ids=dict(paper.external_ids),
        )

    @staticmethod
    def reference_edges(
        rows: Sequence[Sequence[Any]],
        *,
        citing_corpus_id: int,
        citing_s2_id: str,
        sha_map: Mapping[int, str],
    ) -> list[EdgeRecord]:
        return [
            EdgeRecord(
                citing_corpus_id=citing_corpus_id,
                cited_corpus_id=row[0],
                citing_s2_id=citing_s2_id,
                cited_s2_id=sha_map.get(row[0]),
                is_influential=bool(row[1]),
            )
            for row in rows
            if row[0] is not None and sha_map.get(row[0]) is not None
        ]

    @staticmethod
    def citation_edges(
        rows: Sequence[Sequence[Any]],
        *,
        cited_corpus_id: int,
        cited_s2_id: str,
        sha_map: Mapping[int, str],
    ) -> list[EdgeRecord]:
        return [
            EdgeRecord(
                citing_corpus_id=row[0],
                cited_corpus_id=cited_corpus_id,
                citing_s2_id=sha_map.get(row[0]),
                cited_s2_id=cited_s2_id,
                is_influential=bool(row[1]),
            )
            for row in rows
            if row[0] is not None and sha_map.get(row[0]) is not None
        ]

    @staticmethod
    def api_paper(data: Mapping[str, Any]) -> PaperRecord:
        tldr = data.get("tldr")
        tldr_text = tldr.get("text") if isinstance(tldr, Mapping) else None

        open_access_pdf = data.get("openAccessPdf")
        open_access_url = (
            open_access_pdf.get("url") if isinstance(open_access_pdf, Mapping) else None
        )

        authors = data.get("authors") or []
        fields_of_study = data.get("fieldsOfStudy") or data.get("s2FieldsOfStudy") or []
        if fields_of_study and isinstance(fields_of_study[0], Mapping):
            fields_of_study = [item.get("category", "") for item in fields_of_study]

        return PaperRecord(
            s2_id=data.get("paperId"),
            title=data.get("title", ""),
            year=data.get("year"),
            venue=data.get("venue"),
            authors=[
                {"authorId": author.get("authorId"), "name": author.get("name")}
                for author in authors
            ],
            abstract=data.get("abstract"),
            tldr=tldr_text,
            citation_count=data.get("citationCount", 0),
            reference_count=data.get("referenceCount", 0),
            influential_citation_count=data.get("influentialCitationCount", 0),
            is_open_access=data.get("isOpenAccess", False),
            open_access_pdf_url=open_access_url,
            fields_of_study=fields_of_study,
            publication_types=data.get("publicationTypes") or [],
            external_ids=data.get("externalIds") or {},
        )
