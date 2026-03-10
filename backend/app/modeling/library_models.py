"""
Library entry and author models.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.modeling.value_objects import EntryMetadata

if TYPE_CHECKING:
    from app.modeling.catalog_models import EntryTopic, Subject, Venue
    from app.modeling.collection_models import CollectionEntry
    from app.modeling.s2_models import S2Paper


class EntryType(str, PyEnum):
    """BibTeX entry types per official specification."""

    ARTICLE = "article"
    BOOK = "book"
    BOOKLET = "booklet"
    INBOOK = "inbook"
    INCOLLECTION = "incollection"
    INPROCEEDINGS = "inproceedings"
    MANUAL = "manual"
    MASTERSTHESIS = "mastersthesis"
    MISC = "misc"
    PHDTHESIS = "phdthesis"
    PROCEEDINGS = "proceedings"
    TECHREPORT = "techreport"
    UNPUBLISHED = "unpublished"


class Entry(Base):
    """Main library entry."""

    __tablename__ = "entries"
    __table_args__ = (
        Index("ix_entries_year_created", "year", "created_at"),
        Index("ix_entries_type_year", "entry_type", "year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    s2_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    citation_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    entry_type: Mapped[EntryType] = mapped_column(
        Enum(EntryType, name="entry_type", create_constraint=True)
    )
    title: Mapped[str] = mapped_column(Text)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    required_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    optional_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_file: Mapped[str] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    venue_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id"), nullable=True, index=True
    )
    subject_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True, index=True
    )

    authors: Mapped[list["EntryAuthor"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    collections: Mapped[list["CollectionEntry"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    venue: Mapped[Optional["Venue"]] = relationship("Venue", back_populates="entries")
    subject: Mapped[Optional["Subject"]] = relationship(
        "Subject", back_populates="entries"
    )
    topics: Mapped[list["EntryTopic"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    s2_paper: Mapped[Optional["S2Paper"]] = relationship(
        "S2Paper",
        primaryjoin="foreign(Entry.s2_id) == S2Paper.s2_id",
        viewonly=True,
    )

    @property
    def bib_metadata(self) -> EntryMetadata:
        return EntryMetadata(
            required_fields=self.required_fields or {},
            optional_fields=self.optional_fields or {},
        )

    def __repr__(self) -> str:
        return f"<Entry {self.citation_key}>"


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(500), unique=True)
    normalized: Mapped[str] = mapped_column(String(500), index=True)

    entries: Mapped[list["EntryAuthor"]] = relationship(back_populates="author")

    def __repr__(self) -> str:
        return f"<Author {self.name}>"


class EntryAuthor(Base):
    __tablename__ = "entry_authors"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("authors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer)

    entry: Mapped["Entry"] = relationship(back_populates="authors")
    author: Mapped["Author"] = relationship(back_populates="entries")

    def __repr__(self) -> str:
        return f"<EntryAuthor entry={self.entry_id} author={self.author_id}>"
