"""
Entry serialization helpers.
"""

from app.models import Entry
from app.routers.entity_common import entry_authors, entry_venue
from app.schemas.entries import EntryDetailResponse, EntryResponse


def entry_abstract(entry: Entry) -> str | None:
    """Resolve the best available abstract for an entry."""
    optional = entry.optional_fields or {}
    return optional.get("abstract")


def serialize_entry(entry: Entry) -> EntryResponse:
    """Serialize an entry row for list responses."""
    return EntryResponse(
        id=str(entry.id),
        citation_key=entry.citation_key,
        entry_type=entry.entry_type.value,
        title=entry.title,
        year=entry.year,
        authors=entry_authors(entry),
        venue=entry_venue(entry),
        abstract=entry_abstract(entry),
        file_path=entry.file_path,
        read=entry.read or False,
    )


def serialize_entry_detail(entry: Entry) -> EntryDetailResponse:
    """Serialize an entry row for detail responses."""
    required = entry.required_fields or {}
    optional = entry.optional_fields or {}
    return EntryDetailResponse(
        **serialize_entry(entry).model_dump(),
        required_fields=required,
        optional_fields=optional,
        notes=entry.notes,
        source_file=entry.source_file,
    )
