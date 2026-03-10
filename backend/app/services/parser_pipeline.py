"""
Normalization pipeline for parsed BibTeX entries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.models import EntryType
from app.services.parser_catalogs import PROMOTED_FIELDS, REQUIRED_FIELDS


@dataclass(slots=True)
class EntryParseState:
    entry: dict
    source_file: str
    file_metadata: dict[str, str | list[str]]
    citation_key: str
    entry_type_str: str
    entry_type: EntryType = EntryType.MISC
    title: str = ""
    year: int | None = None
    file_path: str | None = None
    authors: list[str] = field(default_factory=list)
    venue_slug: str | None = None
    required_fields: dict[str, str] = field(default_factory=dict)
    optional_fields: dict[str, str] = field(default_factory=dict)
    subject: str | None = None
    topics: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "citation_key": self.citation_key,
            "entry_type": self.entry_type,
            "title": self.title or f"[{self.citation_key}]",
            "year": self.year,
            "file_path": self.file_path,
            "authors": self.authors,
            "required_fields": self.required_fields,
            "optional_fields": self.optional_fields,
            "source_file": self.source_file,
            "subject": self.subject,
            "topics": self.topics,
            "venue_slug": self.venue_slug,
        }


EntryNormalizer = Callable[[EntryParseState], None]


def normalize_entry_type(state: EntryParseState) -> None:
    try:
        state.entry_type = EntryType(state.entry_type_str)
    except ValueError:
        state.entry_type = EntryType.MISC


def normalize_title_and_year(
    state: EntryParseState,
    *,
    clean_latex_string: Callable[[str], str],
) -> None:
    state.title = clean_latex_string(state.entry.get("title", ""))
    year_str = state.entry.get("year", "")

    if not year_str:
        state.year = None
        return

    try:
        year_clean = year_str.split("-")[0].strip()
        state.year = int(year_clean)
    except ValueError:
        state.year = None


def normalize_file_path(state: EntryParseState) -> None:
    raw_file = state.entry.get("file", "").strip()
    if not raw_file:
        state.file_path = None
        return

    if raw_file.startswith(":"):
        parts = raw_file.split(":")
        state.file_path = parts[1].strip() or None if len(parts) >= 2 else None
        return

    state.file_path = raw_file


def normalize_authors(
    state: EntryParseState,
    *,
    parse_authors: Callable[[str], list[str]],
) -> None:
    state.authors = parse_authors(state.entry.get("author", ""))


def normalize_venue(
    state: EntryParseState,
    *,
    resolve_venue: Callable[[str], str | None],
) -> None:
    booktitle = state.entry.get("booktitle", "")
    journal = state.entry.get("journal", "")

    if booktitle:
        state.venue_slug = resolve_venue(booktitle)
    elif journal:
        state.venue_slug = resolve_venue(journal)


def split_required_optional_fields(state: EntryParseState) -> None:
    required_set = REQUIRED_FIELDS.get(state.entry_type_str, set())
    required_fields: dict[str, str] = {}
    optional_fields: dict[str, str] = {}

    for key, value in state.entry.items():
        if key in {"ENTRYTYPE", "ID"} or key in PROMOTED_FIELDS:
            continue

        if key in required_set:
            required_fields[key] = value
        else:
            optional_fields[key] = value

    state.required_fields = required_fields
    state.optional_fields = optional_fields


def apply_file_metadata(state: EntryParseState) -> None:
    subject = state.file_metadata.get("subject")
    topics = state.file_metadata.get("topics", [])

    if isinstance(subject, list):
        subject = subject[0] if subject else None
    if isinstance(topics, str):
        topics = [topics]

    state.subject = subject
    state.topics = list(topics)
