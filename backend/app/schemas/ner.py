"""
Pydantic response schemas for NER entity endpoints.
"""

from pydantic import BaseModel


class NerEntityListItem(BaseModel):
    canonical_id: str
    canonical_surface: str
    label: str
    paper_hits: int
    years_active: int

    model_config = {"from_attributes": True}


class NerEntityLabelStat(BaseModel):
    label: str
    entities: int
    paper_hits: int


class NerEntityDetail(BaseModel):
    canonical_id: str
    canonical_surface: str
    label: str
    first_year: int | None
    last_year: int | None
    paper_hits: int
    mention_total: int
    venue_count: int
    venues: list[str]
    years_active: int

    model_config = {"from_attributes": True}


class NerEntityEntryItem(BaseModel):
    id: str
    citation_key: str
    title: str
    year: int | None
    authors: list[str]
    venue: str | None
    confidence: float
    mention_count: int

    model_config = {"from_attributes": True}


class EntryNerFact(BaseModel):
    canonical_id: str
    canonical_surface: str
    label: str
    confidence: float
    mention_count: int

    model_config = {"from_attributes": True}


class NerIngestResponse(BaseModel):
    entities: int
    facts: int
    unresolved: int
    trends: int = 0
    emergence: int = 0
    flow: int = 0
    bundles: int = 0
    edges: int = 0
    release_id: str
