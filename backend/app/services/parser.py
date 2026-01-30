"""
BibTeX parser service for Folio.

Scans directories recursively for .bib files and parses entries
according to the official BibTeX specification.
"""

import unicodedata
from pathlib import Path
from typing import Iterator

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from app.logging import get_logger
from app.models import EntryType

logger = get_logger(__name__)

# Fields that should be extracted from BibTeX and promoted to columns
PROMOTED_FIELDS = {"title", "year", "file"}

# Required fields per entry type (BibTeX specification)
REQUIRED_FIELDS: dict[str, set[str]] = {
    "article": {"author", "title", "journal", "year"},
    "book": {"title", "publisher", "year"},
    "booklet": {"title"},
    "inbook": {"title", "publisher", "year"},
    "incollection": {"author", "title", "booktitle", "publisher", "year"},
    "inproceedings": {"author", "title", "booktitle", "year"},
    "manual": {"title"},
    "mastersthesis": {"author", "title", "school", "year"},
    "misc": set(),
    "phdthesis": {"author", "title", "school", "year"},
    "proceedings": {"title", "year"},
    "techreport": {"author", "title", "institution", "year"},
    "unpublished": {"author", "title", "note"},
}


def normalize_name(name: str) -> str:
    """Normalize author name: lowercase, remove diacritics."""
    if not name:
        return ""
    # Decompose unicode, remove combining marks
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_name.lower().strip()


def parse_authors(author_string: str) -> list[str]:
    """Parse BibTeX author string into list of author names."""
    if not author_string:
        return []
    # BibTeX separates authors with " and "
    authors = author_string.split(" and ")
    # Clean up each author name
    return [a.strip() for a in authors if a.strip()]


def find_bib_files(directory: Path) -> Iterator[Path]:
    """Recursively find all .bib files in a directory."""
    if not directory.exists():
        logger.warning("Directory does not exist: %s", directory)
        return
    for path in directory.rglob("*.bib"):
        if path.is_file():
            yield path


def parse_bib_file(filepath: Path) -> list[dict]:
    """
    Parse a single .bib file and return list of entry dicts.

    Each entry contains:
    - citation_key: str
    - entry_type: EntryType
    - title: str
    - year: int | None
    - file_path: str | None
    - authors: list[str]
    - required_fields: dict
    - optional_fields: dict
    - source_file: str
    """
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode

    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            bib_database = bibtexparser.load(f, parser=parser)
    except Exception as e:
        logger.error("Error parsing %s: %s", filepath, e)
        return []

    entries = []
    for entry in bib_database.entries:
        try:
            parsed = parse_entry(entry, str(filepath))
            if parsed:
                entries.append(parsed)
        except Exception as e:
            logger.warning(
                "Failed to parse entry %s in %s: %s",
                entry.get("ID", "unknown"),
                filepath,
                e,
            )

    return entries


def parse_entry(entry: dict, source_file: str) -> dict | None:
    """Parse a single BibTeX entry into our schema."""
    entry_type_str = entry.get("ENTRYTYPE", "").lower()
    citation_key = entry.get("ID", "")

    if not citation_key:
        logger.debug("Skipping entry without ID in %s", source_file)
        return None

    # Validate entry type
    try:
        entry_type_enum = EntryType(entry_type_str)
    except ValueError:
        # Default to misc for unknown types
        entry_type_enum = EntryType.MISC
        logger.debug("Unknown entry type '%s', defaulting to misc", entry_type_str)

    # Extract promoted fields
    title = entry.get("title", "").strip()
    year_str = entry.get("year", "")

    year: int | None = None
    if year_str:
        try:
            # Handle year ranges like "2020-2021" by taking first year
            year_clean = year_str.split("-")[0].strip()
            year = int(year_clean)
        except ValueError:
            logger.debug("Invalid year '%s' in %s", year_str, citation_key)

    # File path (absolute path in BibTeX file field)
    file_path = entry.get("file", "").strip() or None

    # Parse authors
    authors = parse_authors(entry.get("author", ""))

    # Separate required vs optional fields
    required_set = REQUIRED_FIELDS.get(entry_type_str, set())
    required_fields: dict[str, str] = {}
    optional_fields: dict[str, str] = {}

    for key, value in entry.items():
        # Skip internal BibTeX parser fields and promoted fields
        if key in {"ENTRYTYPE", "ID"} or key in PROMOTED_FIELDS:
            continue

        if key in required_set:
            required_fields[key] = value
        else:
            optional_fields[key] = value

    return {
        "citation_key": citation_key,
        "entry_type": entry_type_enum,
        "title": title or f"[{citation_key}]",  # Fallback title
        "year": year,
        "file_path": file_path,
        "authors": authors,
        "required_fields": required_fields,
        "optional_fields": optional_fields,
        "source_file": source_file,
    }


def scan_directory(directory: str | Path) -> list[dict]:
    """
    Scan a directory recursively for .bib files and parse all entries.

    Returns a list of parsed entry dicts.
    """
    directory = Path(directory)
    all_entries = []

    for bib_path in find_bib_files(directory):
        entries = parse_bib_file(bib_path)
        all_entries.extend(entries)
        logger.info("Parsed %d entries from %s", len(entries), bib_path.name)

    logger.info("Total: %d entries from %s", len(all_entries), directory)
    return all_entries
