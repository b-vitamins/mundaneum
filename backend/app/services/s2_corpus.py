"""
Compatibility surface for Semantic Scholar corpus access.
"""

from app.services.s2_source_registry import ChainedSource, S2SourceRegistry
from app.services.s2_sources import LiveAPI, LocalCorpus

__all__ = [
    "ChainedSource",
    "LiveAPI",
    "LocalCorpus",
    "S2SourceRegistry",
    "get_data_source",
    "get_local_source",
]


def get_local_source() -> LocalCorpus | None:
    """Return the runtime-owned local corpus source, if configured."""
    from app.services.s2_runtime import get_s2_runtime

    return get_s2_runtime().local_source


def get_data_source() -> ChainedSource:
    """Return the runtime-owned chained data source."""
    from app.services.s2_runtime import get_s2_runtime

    return get_s2_runtime().data_source
