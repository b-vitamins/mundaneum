"""
SQLAlchemy models following BibTeX specification.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


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
    """
    Main entry table following BibTeX standard.

    Required/optional fields stored in JSONB for flexibility.
    Common fields promoted to columns for indexing.
    """

    __tablename__ = "entries"
    __table_args__ = (
        Index("ix_entries_year_created", "year", "created_at"),
        Index("ix_entries_type_year", "entry_type", "year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Link to Semantic Scholar (Shadow Graph)
    s2_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    citation_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    entry_type: Mapped[EntryType] = mapped_column(
        Enum(EntryType, name="entry_type", create_constraint=True)
    )

    # Promoted fields (indexed for search)
    title: Mapped[str] = mapped_column(Text)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # BibTeX fields stored as JSONB
    required_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    optional_fields: Mapped[dict] = mapped_column(JSONB, default=dict)

    # File reference (absolute path)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source tracking
    source_file: Mapped[str] = mapped_column(Text)

    # User data
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Metadata dimensions (extracted from BibTeX fields)
    venue_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id"), nullable=True, index=True
    )
    subject_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True, index=True
    )

    # Relationships
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

    # Relationship to S2Paper (Manual join, no FK constraint in DB)
    s2_paper: Mapped[Optional["S2Paper"]] = relationship(
        "S2Paper",
        primaryjoin="foreign(Entry.s2_id) == S2Paper.s2_id",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Entry {self.citation_key}>"


class Author(Base):
    """Deduplicated author table."""

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
    """Many-to-many: entries <-> authors with position."""

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


class Collection(Base):
    """User-defined collections for organizing entries."""

    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    entries: Mapped[list["CollectionEntry"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Collection {self.name}>"


class CollectionEntry(Base):
    """Many-to-many: collections <-> entries with ordering."""

    __tablename__ = "collection_entries"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    collection: Mapped["Collection"] = relationship(back_populates="entries")
    entry: Mapped["Entry"] = relationship(back_populates="collections")

    def __repr__(self) -> str:
        return (
            f"<CollectionEntry collection={self.collection_id} entry={self.entry_id}>"
        )


class S2Paper(Base):
    """
    Semantic Scholar paper metadata (Shadow Graph).
    stores rich metadata from S2AG for caching and graph purposes.
    """

    __tablename__ = "s2_papers"

    s2_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    venue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Authors list: [{"authorId": "...", "name": "..."}]
    authors: Mapped[list[dict]] = mapped_column(JSONB, default=list)

    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # {"model": "...", "text": "..."}
    tldr: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    reference_count: Mapped[int] = mapped_column(Integer, default=0)
    influential_citation_count: Mapped[int] = mapped_column(Integer, default=0)

    is_open_access: Mapped[bool] = mapped_column(Boolean, default=False)
    # {"url": "...", "status": "..."}
    open_access_pdf: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    fields_of_study: Mapped[list[str]] = mapped_column(JSONB, default=list)
    publication_types: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # {"DOI": "...", "ArXiv": "..."}
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Vector embedding
    embedding: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<S2Paper {self.s2_id} {self.title[:20]}...>"


class S2Citation(Base):
    """
    Edges in the S2 citation graph.
    """

    __tablename__ = "s2_citations"

    source_id: Mapped[str] = mapped_column(
        String, ForeignKey("s2_papers.s2_id", ondelete="CASCADE"), primary_key=True
    )
    target_id: Mapped[str] = mapped_column(
        String, ForeignKey("s2_papers.s2_id", ondelete="CASCADE"), primary_key=True
    )

    # Context snippets where the citation happens
    # e.g. ["Cited in Introduction...", "Used as baseline..."]
    contexts: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # ["methodology", "background", etc.]
    intents: Mapped[list[str]] = mapped_column(JSONB, default=list)

    is_influential: Mapped[bool] = mapped_column(Boolean, default=False)

    source: Mapped["S2Paper"] = relationship("S2Paper", foreign_keys=[source_id])
    target: Mapped["S2Paper"] = relationship("S2Paper", foreign_keys=[target_id])

    def __repr__(self) -> str:
        return f"<S2Citation {self.source_id} -> {self.target_id}>"


class VenueCategory(str, PyEnum):
    """Categories of publication venues."""

    CONFERENCE = "CONFERENCE"
    JOURNAL = "JOURNAL"


class Venue(Base):
    """
    Publication venues extracted from booktitle/journal fields.

    Examples: NeurIPS, ICLR, JMLR, Nature.
    """

    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[VenueCategory] = mapped_column(
        Enum(VenueCategory, name="venue_category", create_type=False)
    )
    # Aliases for matching (e.g., ["NeurIPS", "NIPS", "Advances in Neural..."])
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    entries: Mapped[list["Entry"]] = relationship("Entry", back_populates="venue")

    def __repr__(self) -> str:
        return f"<Venue {self.slug}>"


class Subject(Base):
    """
    Subject areas for books, extracted from file-level @COMMENT.

    Examples: cs-ml-ai, phy-quantum, math-analysis.

    Hierarchical structure:
    - parent_slug: Parent category (e.g., "physics", "computer-science")
    - display_name: Human-readable subarea name (e.g., "Machine Learning & AI")
    """

    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))

    # Hierarchical fields
    parent_slug: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    entries: Mapped[list["Entry"]] = relationship("Entry", back_populates="subject")

    def __repr__(self) -> str:
        return f"<Subject {self.slug}>"


class Topic(Base):
    """
    Curated research topics, extracted from file-level @COMMENT.

    Examples: diffusion, transformers, llm, gnn.
    """

    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))

    entries: Mapped[list["EntryTopic"]] = relationship(back_populates="topic")

    def __repr__(self) -> str:
        return f"<Topic {self.slug}>"


class EntryTopic(Base):
    """Many-to-many: entries <-> topics."""

    __tablename__ = "entry_topics"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
    )

    entry: Mapped["Entry"] = relationship(back_populates="topics")
    topic: Mapped["Topic"] = relationship(back_populates="entries")

    def __repr__(self) -> str:
        return f"<EntryTopic entry={self.entry_id} topic={self.topic_id}>"
