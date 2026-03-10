"""
Entry serialization helpers.
"""

from app.models import Entry
from app.routers.entity_common import entry_authors, entry_venue
from app.schemas.entries import EntryDetailResponse, EntryResponse


def entry_abstract(entry: Entry) -> str | None:
    """Resolve the best available abstract for an entry."""
    return entry.bib_metadata.abstract


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
    metadata = entry.bib_metadata
    return EntryDetailResponse(
        **serialize_entry(entry).model_dump(),
        required_fields=metadata.dump_required(),
        optional_fields=metadata.dump_optional(),
        notes=entry.notes,
        source_file=entry.source_file,
    )
