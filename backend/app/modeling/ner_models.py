"""
NER entity models for extracted named entities from the folio-lab pipeline.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.modeling.library_models import Entry


class NerEntity(Base):
    """Canonical NER entity from the entity atlas."""

    __tablename__ = "ner_entities"
    __table_args__ = (
        Index("ix_ner_entities_label_paper_hits", "label", "paper_hits"),
        Index("ix_ner_entities_surface", "canonical_surface"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    canonical_surface: Mapped[str] = mapped_column(String(500))
    label: Mapped[str] = mapped_column(String(50), index=True)
    first_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    paper_hits: Mapped[int] = mapped_column(Integer, default=0)
    mention_total: Mapped[int] = mapped_column(Integer, default=0)
    venue_count: Mapped[int] = mapped_column(Integer, default=0)
    venues: Mapped[list[str]] = mapped_column(JSONB, default=list)
    years_active: Mapped[int] = mapped_column(Integer, default=0)

    entries: Mapped[list["EntryNerEntity"]] = relationship(
        back_populates="ner_entity", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<NerEntity {self.canonical_surface} ({self.label})>"


class EntryNerEntity(Base):
    """Join table linking entries to NER entities with extraction metadata."""

    __tablename__ = "entry_ner_entities"
    __table_args__ = (
        Index("ix_entry_ner_entities_ner_entity_id", "ner_entity_id"),
        Index("ix_entry_ner_entities_label", "label"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ner_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ner_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    label: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    mention_count: Mapped[int] = mapped_column(Integer, default=1)

    entry: Mapped["Entry"] = relationship(back_populates="ner_entities")
    ner_entity: Mapped["NerEntity"] = relationship(back_populates="entries")

    def __repr__(self) -> str:
        return f"<EntryNerEntity entry={self.entry_id} entity={self.ner_entity_id}>"


class NerRelease(Base):
    """Release metadata for NER pipeline runs."""

    __tablename__ = "ner_releases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    release_id: Mapped[str] = mapped_column(String(100), unique=True)
    product_id: Mapped[str] = mapped_column(String(100))
    run_id: Mapped[str] = mapped_column(String(50))
    entries_seen: Mapped[int] = mapped_column(Integer, default=0)
    mentions_seen: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    manifest: Mapped[dict] = mapped_column(JSONB, default=dict)

    def __repr__(self) -> str:
        return f"<NerRelease {self.release_id}>"
