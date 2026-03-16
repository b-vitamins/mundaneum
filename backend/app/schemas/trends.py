"""
Pydantic response schemas for trends dashboard endpoints.
"""

from typing import Literal

from pydantic import BaseModel


class TrendMoverItem(BaseModel):
    """A single entity row in the movers table."""

    canonical_id: str
    canonical_surface: str
    label: str
    venue: str
    year: int
    prevalence: float
    momentum: float
    paper_hits: int
    change_point: bool
    change_direction: Literal["rising", "falling", "stable"]
    prevalence_z: float

    model_config = {"from_attributes": True}


class TrendPoint(BaseModel):
    year: int
    venue: str
    prevalence: float
    momentum: float
    paper_hits: int


class TrendSparkline(BaseModel):
    """Sparkline data: yearly prevalence for a single entity across all venues."""

    canonical_id: str
    canonical_surface: str
    label: str
    points: list[TrendPoint]


class EmergenceItem(BaseModel):
    """An emerging entity from the watchlist."""

    canonical_id: str
    canonical_surface: str
    label: str
    venue: str
    year: int
    emergence_score: float
    momentum: float
    prevalence: float
    paper_hits: int

    model_config = {"from_attributes": True}


class CrossVenueFlowItem(BaseModel):
    """A cross-venue entity transfer record."""

    canonical_id: str
    canonical_surface: str
    label: str
    source_venue: str
    source_year: int
    target_venue: str
    target_year: int
    lag_years: int
    transfer_score: float

    model_config = {"from_attributes": True}


class TrendsDashboardStats(BaseModel):
    """Summary stats for the trends dashboard header."""

    total_entities: int
    total_trend_rows: int
    emerging_count: int
    venues: list[str]
    labels: list[str]
    year_range: list[int]  # [min_year, max_year]
