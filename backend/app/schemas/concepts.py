"""
Pydantic response schemas for concept graph endpoints.
"""

from typing import Literal

from pydantic import BaseModel


class BundleTopEntity(BaseModel):
    canonical_id: str | None = None
    canonical_surface: str
    label: str
    node_key: str | None = None
    paper_hits: int


class BundleListItem(BaseModel):
    """Summary of a concept bundle for the grid view."""

    bundle_index: int
    bundle_id: str | None = None
    lifecycle: str | None = None
    size: int
    venue_count: int
    venue_coverage: list[str]
    top_entities: list[BundleTopEntity]
    growth_indicator: Literal["growing", "declining", "stable"]

    model_config = {"from_attributes": True}


class BundleDetail(BaseModel):
    """Full detail for a single concept bundle."""

    bundle_index: int
    bundle_id: str | None = None
    lifecycle: str | None = None
    birth_year: int | None = None
    latest_year: int | None = None
    size: int
    latest_year_papers: int
    venue_count: int
    growth_rate: float
    cohesion: float
    internal_edge_weight: int
    external_edge_weight: int
    venue_coverage: list[str]
    members: list[str]
    top_entities: list[BundleTopEntity]
    yearly_paper_counts: dict[str, int]
    previous_year_papers: int

    model_config = {"from_attributes": True}


class CooccurrenceEdgeItem(BaseModel):
    """A co-occurrence edge between two entities."""

    left_node: str
    left_canonical_id: str | None = None
    left_label: str
    right_node: str
    right_canonical_id: str | None = None
    right_label: str
    paper_count: int
    venue: str
    year: int

    model_config = {"from_attributes": True}


class EntityNeighbor(BaseModel):
    """A neighbor entity in the co-occurrence graph."""

    canonical_id: str
    canonical_surface: str
    label: str
    paper_count: int  # co-occurrence count
