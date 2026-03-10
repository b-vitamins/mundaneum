"""
Stable graph domain models.
"""

from dataclasses import dataclass, field


@dataclass(slots=True)
class GraphNode:
    """A node in the citation graph."""

    id: str
    title: str
    year: int | None = None
    venue: str | None = None
    authors: list[str] = field(default_factory=list)
    citation_count: int = 0
    fields_of_study: list[str] = field(default_factory=list)
    in_library: bool = False
    entry_id: str | None = None


@dataclass(slots=True)
class GraphEdge:
    """A directed edge: source cites target."""

    source: str
    target: str
    is_influential: bool = False


@dataclass(slots=True)
class AggregateEntry:
    """A paper surfaced by aggregate analysis."""

    id: str
    title: str
    year: int | None = None
    venue: str | None = None
    authors: list[str] = field(default_factory=list)
    citation_count: int = 0
    frequency: int = 0
    in_library: bool = False
    entry_id: str | None = None


@dataclass(slots=True)
class SimilarityEdge:
    """An undirected similarity edge between two papers."""

    source: str
    target: str
    weight: float


@dataclass(slots=True)
class GraphData:
    """Complete subgraph payload."""

    center_id: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    similarity_edges: list[SimilarityEdge] = field(default_factory=list)
    prior_works: list[AggregateEntry] = field(default_factory=list)
    derivative_works: list[AggregateEntry] = field(default_factory=list)
