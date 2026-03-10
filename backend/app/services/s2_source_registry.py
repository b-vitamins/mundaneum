"""
Composable S2 source ordering and chaining.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.services.s2_protocol import EdgeRecord, PaperRecord, S2DataSource


class ChainedSource:
    """Try each registered source in order and return the first useful value."""

    def __init__(self, sources: list[S2DataSource]):
        self._sources = sources

    async def first_result(self, operation) -> object | None:
        for source in self._sources:
            result = await operation(source)
            if result is not None:
                return result
        return None

    async def get_paper(self, s2_id: str) -> PaperRecord | None:
        return await self.first_result(lambda source: source.get_paper(s2_id))

    async def get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        return await self.first_result(
            lambda source: source.get_paper_by_corpus_id(corpus_id)
        )

    async def get_references(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        return await self.first_result(
            lambda source: source.get_references(s2_id, limit=limit)
        )

    async def get_citations(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        return await self.first_result(
            lambda source: source.get_citations(s2_id, limit=limit)
        )

    async def resolve_id(self, id_type: str, identifier: str) -> str | None:
        return await self.first_result(
            lambda source: source.resolve_id(id_type, identifier)
        )

    async def search(self, query: str, limit: int = 10) -> list[PaperRecord] | None:
        return await self.first_result(lambda source: source.search(query, limit=limit))

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        return await self.first_result(lambda source: source.get_reference_ids(s2_id))


class S2SourceRegistry:
    """Named ordered registry for runtime-owned S2 data sources."""

    def __init__(self, sources: Iterable[tuple[str, S2DataSource]] | None = None):
        self._sources: dict[str, S2DataSource] = {}
        if sources is not None:
            for name, source in sources:
                self.register(name, source)

    def register(self, name: str, source: S2DataSource) -> S2DataSource:
        self._sources[name] = source
        return source

    def get(self, name: str) -> S2DataSource | None:
        return self._sources.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(self._sources.keys())

    def ordered_sources(self) -> list[S2DataSource]:
        return list(self._sources.values())

    def chain(self) -> ChainedSource:
        return ChainedSource(self.ordered_sources())


class SourceRegistry:
    """Compatibility registry for unnamed source chains."""

    def __init__(self, sources: Iterable[S2DataSource] | None = None):
        self._sources = list(sources or [])

    def register(self, source: S2DataSource) -> S2DataSource:
        self._sources.append(source)
        return source

    async def first_result(self, operation) -> object | None:
        return await ChainedSource(self._sources).first_result(operation)

    def chain(self) -> ChainedSource:
        return ChainedSource(self._sources)
