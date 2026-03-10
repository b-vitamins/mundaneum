"""
Compatibility surface for Semantic Scholar corpus types.
"""

from app.services.s2_source_registry import ChainedSource, S2SourceRegistry
from app.services.s2_sources import LiveAPI, LocalCorpus

__all__ = [
    "ChainedSource",
    "LiveAPI",
    "LocalCorpus",
    "S2SourceRegistry",
]
