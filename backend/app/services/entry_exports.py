"""
Entry export and file helpers.
"""

from pathlib import Path

from app.exceptions import NotFoundError
from app.models import Entry
from app.routers.entity_common import entry_authors


def render_bibtex(entry: Entry) -> str:
    """Render a stored entry as BibTeX."""
    lines = [f"@{entry.entry_type.value}{{{entry.citation_key},"]
    lines.append(f"  title = {{{entry.title}}},")

    authors = entry_authors(entry)
    if authors:
        lines.append(f"  author = {{{' and '.join(authors)}}},")

    if entry.year:
        lines.append(f"  year = {{{entry.year}}},")

    for key, value in (entry.required_fields or {}).items():
        if key not in {"title", "author", "year"}:
            lines.append(f"  {key} = {{{value}}},")

    for key, value in (entry.optional_fields or {}).items():
        lines.append(f"  {key} = {{{value}}},")

    if entry.file_path:
        lines.append(f"  file = {{{entry.file_path}}},")

    lines.append("}")
    return "\n".join(lines)


def resolve_pdf_path(entry: Entry) -> Path:
    """Resolve and validate the PDF path for an entry."""
    if not entry.file_path:
        raise NotFoundError("PDF", f"Entry {entry.id} has no associated PDF")

    pdf_path = Path(entry.file_path)
    if not pdf_path.exists():
        raise NotFoundError("PDF file", str(pdf_path))
    if pdf_path.suffix.lower() != ".pdf":
        raise NotFoundError("PDF", "File is not a PDF")
    return pdf_path
