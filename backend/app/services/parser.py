"""
BibTeX parser service for Mundaneum.

Parses bibliography files according to the official BibTeX specification.
"""

import re
import unicodedata
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from pylatexenc.latex2text import LatexNodes2Text

from app.logging import get_logger
from app.models import EntryType
from app.services.bibliography_contract import (
    BibliographySourceFile,
    discover_bibliography_sources,
)
from app.services.parser_catalogs import (
    CONTEXT_SUBAREA_NAMES,
    FULL_SLUG_SUBJECTS,
    SUBAREA_NAMES,
    SUBJECT_PREFIXES,
    VENUE_DATA,
)
from app.services.parser_passes import build_parser_passes, run_parser_passes
from app.services.parser_pipeline import EntryParseState

logger = get_logger(__name__)

# Build reverse lookup: normalized alias -> venue slug
_VENUE_ALIAS_MAP: dict[str, str] = {}
for slug, (_, _, aliases) in VENUE_DATA.items():
    for alias in aliases:
        _VENUE_ALIAS_MAP[alias.lower()] = slug


def parse_subject_name(slug: str) -> tuple[str, str | None, str]:
    """
    Parse a subject slug into parent category, subarea, and display name.

    Handles three cases:
    1. Full-slug matches (e.g., "popular-science" -> standalone category)
    2. Prefix-based splits (e.g., "cs-ml-ai" -> CS / ML & AI)
    3. Context-aware subarea names (e.g., phy-general != cs-general)

    Returns:
        (parent_name, subarea_name, display_name)
    """
    # 1. Check full-slug overrides first
    if slug in FULL_SLUG_SUBJECTS:
        name = FULL_SLUG_SUBJECTS[slug]
        return name, None, name

    # 2. Try prefix-based split
    parts = slug.split("-", 1)
    prefix = parts[0].lower()

    # Get parent category
    parent = SUBJECT_PREFIXES.get(prefix)

    if parent is None:
        # Unknown prefix, treat the whole slug as a standalone category
        name = slug.replace("-", " ").replace("_", " ").title()
        return name, None, name

    if len(parts) == 1:
        # No subarea, just the parent
        return parent, None, parent

    # 3. Get subarea name with context awareness
    subarea_slug = parts[1]
    context_key = f"{prefix}:{subarea_slug}"

    # Try context-specific first, then generic, then title-case fallback
    subarea = (
        CONTEXT_SUBAREA_NAMES.get(context_key)
        or SUBAREA_NAMES.get(subarea_slug)
        or subarea_slug.replace("-", " ").title()
    )

    return parent, subarea, subarea


def normalize_venue(venue_str: str) -> str | None:
    """
    Normalize a venue string to a known slug.

    Returns venue slug or None if not recognized.
    """
    if not venue_str:
        return None

    # Normalize: lowercase, strip
    normalized = venue_str.lower().strip()

    # Direct lookup
    if normalized in _VENUE_ALIAS_MAP:
        return _VENUE_ALIAS_MAP[normalized]

    # Check if any alias is a substring
    for alias, slug in _VENUE_ALIAS_MAP.items():
        if alias in normalized or normalized in alias:
            return slug

    return None


def get_venue_info(slug: str) -> tuple[str, str, list[str]] | None:
    """Get venue display name, category, and aliases for a slug."""
    return VENUE_DATA.get(slug)


# Singleton converter for LaTeX to text
_latex_converter = LatexNodes2Text()


def clean_latex_string(text: str) -> str:
    r"""
    Clean LaTeX encoded strings to proper Unicode.

    Handles common LaTeX patterns like:
    - \'{e} -> é
    - \"{o} -> ö
    - {\ss} -> ß
    - Curly brace wrappers: {Something} -> Something

    Falls back to original text if conversion fails.
    """
    if not text:
        return ""

    try:
        # Use pylatexenc for robust LaTeX -> Unicode conversion
        cleaned = _latex_converter.latex_to_text(text)

        # Clean up any remaining curly braces (common in BibTeX titles)
        cleaned = re.sub(r"\{([^}]*)\}", r"\1", cleaned)

        # Normalize whitespace
        cleaned = " ".join(cleaned.split())

        return cleaned.strip()
    except Exception:
        # Fallback: just remove curly braces and return
        fallback = re.sub(r"\{([^}]*)\}", r"\1", text)
        return " ".join(fallback.split()).strip()


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
    # Clean up each author name and convert LaTeX to Unicode
    return [clean_latex_string(a) for a in authors if a.strip()]


_PARSER_PASSES = build_parser_passes(
    clean_latex_string=clean_latex_string,
    parse_authors=parse_authors,
    resolve_venue=normalize_venue,
)


def build_source_file(
    filepath: Path,
    *,
    root: Path | None = None,
    role: str = "canonical",
    subject: str | None = None,
    topics: tuple[str, ...] = (),
) -> BibliographySourceFile:
    """Construct a stable parse context for one BibTeX file."""
    root = (root or filepath.parent).resolve()
    return BibliographySourceFile(
        path=filepath.resolve(),
        source_file=filepath.resolve().relative_to(root).as_posix(),
        role=role,
        subject=subject,
        topics=topics,
    )


def parse_bib_file(
    filepath: Path,
    *,
    source: BibliographySourceFile | None = None,
) -> list[dict]:
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
    - source_role: str
    - subject: str | None (from bibliography contract)
    - topics: list[str] (from bibliography contract)
    - venue_slug: str | None (normalized from booktitle/journal)
    """
    source = source or build_source_file(filepath)
    filepath = source.path
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode

    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            raw_content = f.read()
    except Exception as e:
        logger.error("Error reading %s: %s", filepath, e)
        return []

    try:
        bib_database = bibtexparser.loads(raw_content, parser=parser)
    except Exception as e:
        logger.error("Error parsing %s: %s", filepath, e)
        return []

    entries = []
    for entry in bib_database.entries:
        try:
            parsed = parse_entry(
                entry,
                source_file=source.source_file,
                source_role=source.role,
                file_metadata={
                    "subject": source.subject,
                    "topics": list(source.topics),
                },
            )
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


def parse_entry(
    entry: dict,
    source_file: str,
    source_role: str = "canonical",
    file_metadata: dict[str, str | list[str]] | None = None,
) -> dict | None:
    """Parse a single BibTeX entry into our schema."""
    entry_type_str = entry.get("ENTRYTYPE", "").lower()
    citation_key = entry.get("ID", "")

    if not citation_key:
        logger.debug("Skipping entry without ID in %s", source_file)
        return None

    state = EntryParseState(
        entry=entry,
        source_file=source_file,
        source_role=source_role,
        file_metadata=file_metadata or {},
        citation_key=citation_key,
        entry_type_str=entry_type_str,
    )

    run_parser_passes(state, _PARSER_PASSES)

    if state.entry_type is EntryType.MISC and entry_type_str:
        logger.debug("Unknown entry type '%s', defaulting to misc", entry_type_str)
    if entry.get("year") and state.year is None:
        logger.debug("Invalid year '%s' in %s", entry.get("year", ""), citation_key)

    return state.as_dict()


def scan_directory(directory: str | Path) -> list[dict]:
    """
    Scan a directory recursively for .bib files and parse all entries.

    Returns a list of parsed entry dicts.
    """
    directory = Path(directory)
    all_entries = []

    for source in discover_bibliography_sources(directory):
        entries = parse_bib_file(source.path, source=source)
        all_entries.extend(entries)
        logger.info("Parsed %d entries from %s", len(entries), source.source_file)

    logger.info("Total: %d entries from %s", len(all_entries), directory)
    return all_entries
