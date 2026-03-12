"""
Catalog models for venues, subjects, and topics.
"""

from __future__ import annotations

import uuid
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.modeling.library_models import Entry


class VenueCategory(str, PyEnum):
    CONFERENCE = "CONFERENCE"
    JOURNAL = "JOURNAL"


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[VenueCategory] = mapped_column(
        Enum(VenueCategory, name="venue_category", create_type=False)
    )
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    entries: Mapped[list["Entry"]] = relationship("Entry", back_populates="venue")

    def __repr__(self) -> str:
        return f"<Venue {self.slug}>"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    parent_slug: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    entries: Mapped[list["Entry"]] = relationship("Entry", back_populates="subject")

    def __repr__(self) -> str:
        return f"<Subject {self.slug}>"


class Topic(Base):
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
