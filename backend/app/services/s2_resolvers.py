"""
Resolver policies for entry-to-paper matching.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from app.models import Entry
from app.services.s2_transport import S2Transport

logger = logging.getLogger(__name__)


@runtime_checkable
class Resolver(Protocol):
    """Map a library Entry to an S2 paper ID."""

    async def resolve(self, entry: Entry, transport: S2Transport) -> str | None: ...


class DOIResolver:
    """Resolve via DOI — deterministic, sub-second."""

    async def resolve(self, entry: Entry, transport: S2Transport) -> str | None:
        doi = extract_identifier(entry, "doi")
        if not doi:
            return None
        data = await transport.get(f"paper/DOI:{doi}", params={"fields": "paperId"})
        if data and data.get("paperId"):
            logger.info("Resolved '%s' via DOI:%s", entry.title[:40], doi)
            return data["paperId"]
        return None


class ArXivResolver:
    """Resolve via ArXiv ID — deterministic, sub-second."""

    async def resolve(self, entry: Entry, transport: S2Transport) -> str | None:
        arxiv_id = extract_identifier(entry, "arxiv", "eprint")
        if not arxiv_id:
            return None
        data = await transport.get(
            f"paper/ARXIV:{arxiv_id}",
            params={"fields": "paperId"},
        )
        if data and data.get("paperId"):
            logger.info("Resolved '%s' via ArXiv:%s", entry.title[:40], arxiv_id)
            return data["paperId"]
        return None


class TitleResolver:
    """Fallback: search by title — 1-2s via direct API."""

    async def resolve(self, entry: Entry, transport: S2Transport) -> str | None:
        results = await transport.search(entry.title, limit=3)
        if not results:
            return None

        query_lower = entry.title.lower().strip()
        for result in results:
            title = (result.get("title") or "").lower().strip()
            if title and title_similarity(query_lower, title) > 0.7:
                s2_id = result.get("paperId")
                if s2_id:
                    logger.info("Resolved '%s' via title search", entry.title[:40])
                    return s2_id

        first = results[0].get("paperId")
        if first:
            logger.info(
                "Resolved '%s' via title search (best-effort)",
                entry.title[:40],
            )
            return first
        return None


def extract_identifier(entry: Entry, *field_names: str) -> str | None:
    """Extract an identifier from an entry's BibTeX fields."""
    for fields in [entry.required_fields or {}, entry.optional_fields or {}]:
        for name in field_names:
            value = (
                fields.get(name) or fields.get(name.upper()) or fields.get(name.lower())
            )
            if value and isinstance(value, str) and value.strip():
                return value.strip()
    return None


def title_similarity(left: str, right: str) -> float:
    """Jaccard similarity over word sets — fast and good enough."""
    left_words, right_words = set(left.split()), set(right.split())
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / len(left_words | right_words)


def default_resolvers() -> list[Resolver]:
    """Return the default resolver chain in priority order."""
    return [
        DOIResolver(),
        ArXivResolver(),
        TitleResolver(),
    ]
