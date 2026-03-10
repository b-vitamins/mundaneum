"""
Registry utilities for composing S2 data sources.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from app.services.s2_protocol import S2DataSource

ResultT = TypeVar("ResultT")


class SourceRegistry:
    """Ordered S2 source registry with first-result resolution semantics."""

    def __init__(self, sources: Sequence[S2DataSource]):
        self._sources = list(sources)

    @property
    def sources(self) -> list[S2DataSource]:
        return list(self._sources)

    async def first_result(
        self,
        resolver: Callable[[S2DataSource], Awaitable[ResultT | None]],
    ) -> ResultT | None:
        for source in self._sources:
            result = await resolver(source)
            if result is not None:
                return result
        return None
