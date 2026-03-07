"""
S2 Data Source Protocol — the generic interface for scholarly data access.

Design (Sussman, "Software Design for Flexibility"):
  - A single protocol with multiple implementations.
  - None  = "I don't have this data" → try the next source.
  - []    = "I looked, nothing exists" → stop.
  - Implementations are composed, not selected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PaperRecord:
    """Canonical paper representation across all data sources."""

    corpus_id: int | None = None
    s2_id: str | None = None  # 40-char SHA
    title: str = ""
    year: int | None = None
    venue: str | None = None
    authors: list[dict] = field(default_factory=list)
    abstract: str | None = None
    tldr: str | None = None
    citation_count: int = 0
    reference_count: int = 0
    influential_citation_count: int = 0
    is_open_access: bool = False
    open_access_pdf_url: str | None = None
    fields_of_study: list[str] = field(default_factory=list)
    publication_types: list[str] = field(default_factory=list)
    external_ids: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeRecord:
    """A single citation edge: source cites target."""

    citing_corpus_id: int | None = None
    cited_corpus_id: int | None = None
    citing_s2_id: str | None = None
    cited_s2_id: str | None = None
    is_influential: bool = False


@runtime_checkable
class S2DataSource(Protocol):
    """Generic data source for S2 paper data.

    Implementations may be backed by a local corpus dump (DuckDB),
    a hot cache (PostgreSQL), or the live API.

    The ChainedSource combinator tries each in order —
    first non-None result wins.

    Convention:
      - Return None  → "I don't have this data, try elsewhere"
      - Return []    → "I looked, there's genuinely nothing"
      - Return obj   → "Here's your data"
    """

    async def get_paper(self, s2_id: str) -> PaperRecord | None:
        """Full paper metadata by S2 paper ID (SHA)."""
        ...

    async def get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        """Full paper metadata by corpus ID (integer)."""
        ...

    async def get_references(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        """Papers cited by s2_id. None = unknown, [] = no references."""
        ...

    async def get_citations(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        """Papers citing s2_id. None = unknown, [] = no citations."""
        ...

    async def resolve_id(self, id_type: str, identifier: str) -> str | None:
        """Map an external ID (DOI, ArXiv, title) to an S2 paper ID (SHA).

        id_type: one of 'DOI', 'ArXiv', 'PubMed', 'DBLP', 'MAG', 'title'
        """
        ...

    async def search(self, query: str, limit: int = 10) -> list[PaperRecord] | None:
        """Search papers by title/keyword."""
        ...

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        """Fast path: just the set of cited paper IDs (for Jaccard).

        Default implementation derives from get_references().
        Corpus implementations can override for efficiency.
        """
        refs = await self.get_references(s2_id)
        if refs is None:
            return None
        return {e.cited_s2_id for e in refs if e.cited_s2_id}
