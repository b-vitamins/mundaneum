"""
Shared request/response models for entry endpoints.
"""

from pydantic import BaseModel, Field


class AuthorRef(BaseModel):
    """Minimal author reference for linking entry views to author pages."""

    id: str
    name: str


class EntryResponse(BaseModel):
    """Response model for entry list items."""

    id: str
    citation_key: str
    entry_type: str
    title: str
    year: int | None = None
    authors: list[str]
    author_refs: list[AuthorRef] = Field(default_factory=list)
    venue: str | None = None
    abstract: str | None = None
    file_path: str | None = None
    read: bool = False

    model_config = {"from_attributes": True}


class EntryDetailResponse(EntryResponse):
    """Response model for entry detail view."""

    required_fields: dict
    optional_fields: dict
    notes: str | None = None
    source_file: str


class NotesRequest(BaseModel):
    """Request model for updating notes."""

    notes: str


class ReadRequest(BaseModel):
    """Request model for updating read status."""

    read: bool


class ReadResponse(BaseModel):
    """Response for read status update."""

    id: str
    read: bool


class NotesResponse(BaseModel):
    """Response for notes update."""

    id: str
    notes: str


class S2MetaResponse(BaseModel):
    """S2 metadata with sync status for progressive loading."""

    sync_status: str
    s2_id: str | None = None
    title: str | None = None
    abstract: str | None = None
    tldr: str | None = None
    citation_count: int | None = None
    reference_count: int | None = None
    influential_citation_count: int | None = None
    fields_of_study: list[str] = []
    publication_types: list[str] = []
    is_open_access: bool = False
    open_access_pdf_url: str | None = None
    external_ids: dict = {}
    s2_url: str | None = None


class S2PaperResponse(BaseModel):
    s2_id: str
    title: str
    year: int | None = None
    venue: str | None = None
    authors: list[dict]
    abstract: str | None = None
    tldr: dict | None = None
    citation_count: int
    is_influential: bool = False
    contexts: list[str] = []
    intents: list[str] = []

    model_config = {"from_attributes": True}
