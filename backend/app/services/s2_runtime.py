"""
Runtime wiring for Semantic Scholar services.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.services.s2_protocol import S2DataSource

logger = logging.getLogger(__name__)


class SyncRegistry:
    """Explicit owner of in-flight entry sync state."""

    def __init__(self):
        self._events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def claim(self, entry_id: str) -> bool:
        """Mark an entry as syncing. Returns False when already claimed."""
        async with self._lock:
            if entry_id in self._events:
                return False
            self._events[entry_id] = asyncio.Event()
            return True

    async def release(self, entry_id: str) -> None:
        """Release an in-flight sync claim."""
        async with self._lock:
            event = self._events.pop(entry_id, None)
        if event is not None:
            event.set()


@dataclass(slots=True)
class S2Runtime:
    """Concrete S2 runtime dependencies for the process."""

    transport: "S2Transport"
    local_source: "LocalCorpus | None"
    data_source: "ChainedSource"
    orchestrator: "SyncOrchestrator"

    async def close(self) -> None:
        await self.transport.close()


def build_s2_runtime() -> S2Runtime:
    """Build a fully wired S2 runtime with shared transport/source state."""
    from app.services.s2_corpus import ChainedSource, LiveAPI, LocalCorpus
    from app.services.s2_resolvers import default_resolvers
    from app.services.s2_sync import create_sync_orchestrator
    from app.services.s2_transport import S2Transport

    transport = S2Transport(
        api_key=settings.s2_api_key,
        rate_limit=settings.s2_rate_limit,
    )

    local_source: LocalCorpus | None = None
    sources: list[S2DataSource] = []
    corpus_path = Path(settings.s2_corpus_path)

    if corpus_path.exists():
        try:
            local_source = LocalCorpus(corpus_path)
            sources.append(local_source)
            logger.info("S2 runtime: LocalCorpus loaded (%s)", corpus_path)
        except Exception as exc:
            logger.warning("S2 runtime: LocalCorpus failed to load: %s", exc)
    else:
        logger.info("S2 runtime: DuckDB not found at %s, using API only", corpus_path)

    live_api = LiveAPI(transport)
    sources.append(live_api)
    data_source = ChainedSource(sources)

    orchestrator = create_sync_orchestrator(
        source=data_source,
        sync_registry=SyncRegistry(),
        transport=transport,
        resolvers=default_resolvers(),
    )

    return S2Runtime(
        transport=transport,
        local_source=local_source,
        data_source=data_source,
        orchestrator=orchestrator,
    )


@lru_cache(maxsize=1)
def get_s2_runtime() -> S2Runtime:
    """Return the process-wide S2 runtime."""
    return build_s2_runtime()
