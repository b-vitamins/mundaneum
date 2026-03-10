"""
Mapping helpers for local and live S2 corpus records.
"""

from __future__ import annotations

from typing import Any

from app.services.s2_protocol import EdgeRecord, PaperRecord


def paper_record_from_row(
    row: tuple,
    *,
    corpus_id: int,
    s2_id: str | None,
) -> PaperRecord:
    """Convert a base paper row into a PaperRecord."""
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


def enrich_paper_record(
    base: PaperRecord,
    *,
    abstract_row: tuple | None,
    tldr_row: tuple | None,
    author_rows: list[tuple],
) -> PaperRecord:
    """Attach optional text and author data to a base PaperRecord."""
    return PaperRecord(
        corpus_id=base.corpus_id,
        s2_id=base.s2_id,
        title=base.title,
        year=base.year,
        venue=base.venue,
        authors=[{"authorId": row[0], "name": row[1]} for row in author_rows],
        abstract=abstract_row[0] if abstract_row else None,
        tldr=tldr_row[0] if tldr_row else None,
        citation_count=base.citation_count,
        reference_count=base.reference_count,
        influential_citation_count=base.influential_citation_count,
        is_open_access=base.is_open_access,
        open_access_pdf_url=base.open_access_pdf_url,
        fields_of_study=list(base.fields_of_study),
        publication_types=list(base.publication_types),
        external_ids=dict(base.external_ids),
    )


def reference_edges_from_rows(
    rows: list[tuple],
    *,
    citing_corpus_id: int,
    citing_s2_id: str,
    sha_map: dict[int, str],
) -> list[EdgeRecord]:
    """Map citation rows into outgoing reference edges."""
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


def citation_edges_from_rows(
    rows: list[tuple],
    *,
    cited_corpus_id: int,
    cited_s2_id: str,
    sha_map: dict[int, str],
) -> list[EdgeRecord]:
    """Map citation rows into incoming citation edges."""
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


def api_dict_to_paper(data: dict[str, Any]) -> PaperRecord:
    """Convert an S2 API response dict to a PaperRecord."""
    tldr = data.get("tldr")
    tldr_text = tldr.get("text") if isinstance(tldr, dict) else None

    oa_pdf = data.get("openAccessPdf")
    oa_url = oa_pdf.get("url") if isinstance(oa_pdf, dict) else None

    authors = data.get("authors") or []

    fields_of_study = data.get("fieldsOfStudy") or data.get("s2FieldsOfStudy") or []
    if fields_of_study and isinstance(fields_of_study[0], dict):
        fields_of_study = [field.get("category", "") for field in fields_of_study]

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
        open_access_pdf_url=oa_url,
        fields_of_study=fields_of_study,
        publication_types=data.get("publicationTypes") or [],
        external_ids=data.get("externalIds") or {},
    )
