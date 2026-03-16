"""
Concept graph models: bundles and co-occurrence edges.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NerBundle(Base):
    """Concept cluster from bundle_table.jsonl."""

    __tablename__ = "ner_bundles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bundle_index: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    bundle_id: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    lifecycle: Mapped[str] = mapped_column(String(32), default="stable")
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    latest_year_papers: Mapped[int] = mapped_column(Integer, default=0)
    venue_count: Mapped[int] = mapped_column(Integer, default=0)
    growth_rate: Mapped[float] = mapped_column(Float, default=0.0)
    cohesion: Mapped[float] = mapped_column(Float, default=0.0)
    internal_edge_weight: Mapped[int] = mapped_column(Integer, default=0)
    external_edge_weight: Mapped[int] = mapped_column(Integer, default=0)
    venue_coverage: Mapped[list[str]] = mapped_column(JSONB, default=list)
    members: Mapped[list[str]] = mapped_column(JSONB, default=list)
    top_entities: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    yearly_paper_counts: Mapped[dict] = mapped_column(JSONB, default=dict)
    previous_year_papers: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<NerBundle {self.bundle_index} (size={self.size})>"


class NerCooccurrenceEdge(Base):
    """Entity co-occurrence edge from cooccurrence_edges.jsonl."""

    __tablename__ = "ner_cooccurrence_edges"
    __table_args__ = (
        Index("ix_ner_cooccurrence_edges_nodes", "left_node", "right_node"),
        Index("ix_ner_cooccurrence_edges_venue_year", "venue", "year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    left_node: Mapped[str] = mapped_column(String(100), index=True)
    right_node: Mapped[str] = mapped_column(String(100), index=True)
    left_label: Mapped[str] = mapped_column(String(50))
    right_label: Mapped[str] = mapped_column(String(50))
    paper_count: Mapped[int] = mapped_column(Integer, default=0)
    venue: Mapped[str] = mapped_column(String(50), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)

    def __repr__(self) -> str:
        return f"<NerCooccurrenceEdge {self.left_node} <-> {self.right_node}>"
