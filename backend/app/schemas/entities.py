"""
Shared API schemas for author, venue, subject, and topic views.
"""

from pydantic import BaseModel


class AuthorListItem(BaseModel):
    id: str
    name: str
    entry_count: int

    model_config = {"from_attributes": True}


class AuthorDetail(BaseModel):
    id: str
    name: str
    entry_count: int


class AuthorEntryItem(BaseModel):
    id: str
    citation_key: str
    entry_type: str
    title: str
    year: int | None
    venue: str | None
    read: bool

    model_config = {"from_attributes": True}


class VenueListItem(BaseModel):
    id: str
    slug: str
    name: str
    category: str
    entry_count: int

    model_config = {"from_attributes": True}


class VenueDetail(BaseModel):
    id: str
    slug: str
    name: str
    category: str
    aliases: list[str]
    url: str | None
    entry_count: int


class VenueEntryItem(BaseModel):
    id: str
    citation_key: str
    entry_type: str
    title: str
    year: int | None
    authors: list[str]
    read: bool

    model_config = {"from_attributes": True}


class SubjectListItem(BaseModel):
    id: str
    slug: str
    name: str
    parent_slug: str | None = None
    display_name: str | None = None
    entry_count: int

    model_config = {"from_attributes": True}


class SubjectDetail(BaseModel):
    id: str
    slug: str
    name: str
    entry_count: int


class SubjectEntryItem(BaseModel):
    id: str
    citation_key: str
    entry_type: str
    title: str
    year: int | None
    authors: list[str]
    venue: str | None
    read: bool

    model_config = {"from_attributes": True}


class TopicListItem(BaseModel):
    id: str
    slug: str
    name: str
    entry_count: int

    model_config = {"from_attributes": True}


class TopicDetail(BaseModel):
    id: str
    slug: str
    name: str
    entry_count: int


class TopicEntryItem(BaseModel):
    id: str
    citation_key: str
    entry_type: str
    title: str
    year: int | None
    authors: list[str]
    venue: str | None
    read: bool

    model_config = {"from_attributes": True}
