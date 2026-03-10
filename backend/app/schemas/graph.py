"""
Graph API schemas.
"""

from pydantic import BaseModel

from app.services.graph_models import GraphData


class GraphNodeResponse(BaseModel):
    id: str
    title: str
    year: int | None = None
    venue: str | None = None
    authors: list[str] = []
    citation_count: int = 0
    fields_of_study: list[str] = []
    in_library: bool = False
    entry_id: str | None = None


class GraphEdgeResponse(BaseModel):
    source: str
    target: str
    is_influential: bool = False


class AggregateEntryResponse(BaseModel):
    id: str
    title: str
    year: int | None = None
    venue: str | None = None
    authors: list[str] = []
    citation_count: int = 0
    frequency: int = 0
    in_library: bool = False
    entry_id: str | None = None


class SimilarityEdgeResponse(BaseModel):
    source: str
    target: str
    weight: float


class GraphResponse(BaseModel):
    center_id: str
    nodes: list[GraphNodeResponse] = []
    edges: list[GraphEdgeResponse] = []
    prior_works: list[AggregateEntryResponse] = []
    derivative_works: list[AggregateEntryResponse] = []
    similarity_edges: list[SimilarityEdgeResponse] = []


def graph_response_from_data(graph_data: GraphData) -> GraphResponse:
    """Project graph domain data into the API schema."""
    return GraphResponse(
        center_id=graph_data.center_id,
        nodes=[
            GraphNodeResponse(
                id=node.id,
                title=node.title,
                year=node.year,
                venue=node.venue,
                authors=node.authors,
                citation_count=node.citation_count,
                fields_of_study=node.fields_of_study,
                in_library=node.in_library,
                entry_id=node.entry_id,
            )
            for node in graph_data.nodes
        ],
        edges=[
            GraphEdgeResponse(
                source=edge.source,
                target=edge.target,
                is_influential=edge.is_influential,
            )
            for edge in graph_data.edges
        ],
        prior_works=[
            AggregateEntryResponse(
                id=entry.id,
                title=entry.title,
                year=entry.year,
                venue=entry.venue,
                authors=entry.authors,
                citation_count=entry.citation_count,
                frequency=entry.frequency,
                in_library=entry.in_library,
                entry_id=entry.entry_id,
            )
            for entry in graph_data.prior_works
        ],
        derivative_works=[
            AggregateEntryResponse(
                id=entry.id,
                title=entry.title,
                year=entry.year,
                venue=entry.venue,
                authors=entry.authors,
                citation_count=entry.citation_count,
                frequency=entry.frequency,
                in_library=entry.in_library,
                entry_id=entry.entry_id,
            )
            for entry in graph_data.derivative_works
        ],
        similarity_edges=[
            SimilarityEdgeResponse(
                source=edge.source,
                target=edge.target,
                weight=round(edge.weight, 4),
            )
            for edge in graph_data.similarity_edges
        ],
    )
