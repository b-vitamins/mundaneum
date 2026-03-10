"""
Semantic Scholar cache models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.modeling.value_objects import OpenAccessPDFData, S2TLDRData


class S2Paper(Base):
    __tablename__ = "s2_papers"

    s2_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    venue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    authors: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tldr: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    reference_count: Mapped[int] = mapped_column(Integer, default=0)
    influential_citation_count: Mapped[int] = mapped_column(Integer, default=0)
    is_open_access: Mapped[bool] = mapped_column(Boolean, default=False)
    open_access_pdf: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    fields_of_study: Mapped[list[str]] = mapped_column(JSONB, default=list)
    publication_types: Mapped[list[str]] = mapped_column(JSONB, default=list)
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    @property
    def tldr_data(self) -> S2TLDRData | None:
        if self.tldr is None:
            return None
        return S2TLDRData.model_validate(self.tldr)

    @property
    def open_access_pdf_data(self) -> OpenAccessPDFData | None:
        if self.open_access_pdf is None:
            return None
        return OpenAccessPDFData.model_validate(self.open_access_pdf)

    def __repr__(self) -> str:
        return f"<S2Paper {self.s2_id} {self.title[:20]}...>"


class S2Citation(Base):
    __tablename__ = "s2_citations"

    source_id: Mapped[str] = mapped_column(
        String, ForeignKey("s2_papers.s2_id", ondelete="CASCADE"), primary_key=True
    )
    target_id: Mapped[str] = mapped_column(
        String, ForeignKey("s2_papers.s2_id", ondelete="CASCADE"), primary_key=True
    )
    contexts: Mapped[list[str]] = mapped_column(JSONB, default=list)
    intents: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_influential: Mapped[bool] = mapped_column(Boolean, default=False)

    source: Mapped["S2Paper"] = relationship("S2Paper", foreign_keys=[source_id])
    target: Mapped["S2Paper"] = relationship("S2Paper", foreign_keys=[target_id])

    def __repr__(self) -> str:
        return f"<S2Citation {self.source_id} -> {self.target_id}>"
