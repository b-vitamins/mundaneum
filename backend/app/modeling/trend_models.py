"""
Trend and signal models for the NER signals-product pipeline.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NerTrend(Base):
    """Per-entity, per-venue, per-year trend row from trend_table.jsonl."""

    __tablename__ = "ner_trends"
    __table_args__ = (
        Index("ix_ner_trends_entity_venue_year", "canonical_id", "venue", "year"),
        Index("ix_ner_trends_label_venue_year", "label", "venue", "year"),
        Index("ix_ner_trends_node_key", "node_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_id: Mapped[str] = mapped_column(String(64), index=True)
    canonical_surface: Mapped[str] = mapped_column(String(500))
    label: Mapped[str] = mapped_column(String(50), index=True)
    venue: Mapped[str] = mapped_column(String(50), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    paper_hits: Mapped[int] = mapped_column(Integer, default=0)
    prevalence: Mapped[float] = mapped_column(Float, default=0.0)
    momentum: Mapped[float] = mapped_column(Float, default=0.0)
    rolling_mean_3: Mapped[float] = mapped_column(Float, default=0.0)
    weighted_prevalence: Mapped[float] = mapped_column(Float, default=0.0)
    prevalence_z_by_year_label: Mapped[float] = mapped_column(Float, default=0.0)
    change_point: Mapped[bool] = mapped_column(Boolean, default=False)
    change_direction: Mapped[str] = mapped_column(String(20), default="stable")
    novelty: Mapped[int] = mapped_column(Integer, default=0)
    novelty_score: Mapped[float] = mapped_column(Float, default=0.0)
    persistence_streak: Mapped[int] = mapped_column(Integer, default=0)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    mention_density: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_sum: Mapped[float] = mapped_column(Float, default=0.0)
    cross_venue_transfer: Mapped[float] = mapped_column(Float, default=0.0)
    papers_in_venue_year: Mapped[int] = mapped_column(Integer, default=0)
    node_key: Mapped[str] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"<NerTrend {self.canonical_surface} {self.venue}/{self.year}>"


class NerEmergence(Base):
    """Emerging entity from emergence_watchlist.jsonl."""

    __tablename__ = "ner_emergence"
    __table_args__ = (
        Index("ix_ner_emergence_entity_venue_year", "canonical_id", "venue", "year"),
        Index("ix_ner_emergence_label_venue_year", "label", "venue", "year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_id: Mapped[str] = mapped_column(String(64), index=True)
    canonical_surface: Mapped[str] = mapped_column(String(500))
    label: Mapped[str] = mapped_column(String(50), index=True)
    venue: Mapped[str] = mapped_column(String(50), index=True)
    year: Mapped[int] = mapped_column(Integer)
    emergence_score: Mapped[float] = mapped_column(Float, default=0.0)
    momentum: Mapped[float] = mapped_column(Float, default=0.0)
    prevalence: Mapped[float] = mapped_column(Float, default=0.0)
    prevalence_z_by_year_label: Mapped[float] = mapped_column(Float, default=0.0)
    paper_hits: Mapped[int] = mapped_column(Integer, default=0)
    cross_venue_transfer: Mapped[float] = mapped_column(Float, default=0.0)
    novelty: Mapped[int] = mapped_column(Integer, default=0)
    node_key: Mapped[str] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"<NerEmergence {self.canonical_surface} ({self.emergence_score:.3f})>"


class NerCrossVenueFlow(Base):
    """Cross-venue entity transfer from cross_venue_flow.jsonl."""

    __tablename__ = "ner_cross_venue_flow"
    __table_args__ = (
        Index(
            "ix_ner_cross_venue_flow_entity_source_target",
            "canonical_id",
            "source_venue",
            "target_venue",
        ),
        Index(
            "ix_ner_cross_venue_flow_label_source_target",
            "label",
            "source_venue",
            "target_venue",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_id: Mapped[str] = mapped_column(String(64), index=True)
    canonical_surface: Mapped[str] = mapped_column(String(500))
    label: Mapped[str] = mapped_column(String(50))
    source_venue: Mapped[str] = mapped_column(String(50), index=True)
    source_year: Mapped[int] = mapped_column(Integer)
    target_venue: Mapped[str] = mapped_column(String(50), index=True)
    target_year: Mapped[int] = mapped_column(Integer)
    lag_years: Mapped[int] = mapped_column(Integer, default=0)
    transfer_score: Mapped[float] = mapped_column(Float, default=0.0)
    target_prevalence: Mapped[float] = mapped_column(Float, default=0.0)
    node_key: Mapped[str] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"<NerCrossVenueFlow {self.canonical_surface} {self.source_venue}->{self.target_venue}>"
