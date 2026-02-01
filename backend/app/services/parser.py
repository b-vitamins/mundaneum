"""
BibTeX parser service for Folio.

Scans directories recursively for .bib files and parses entries
according to the official BibTeX specification.
"""

import re
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

# Venue normalization: slug -> (display_name, category, aliases)
VENUE_DATA: dict[str, tuple[str, str, list[str]]] = {
    # Conferences
    "neurips": (
        "NeurIPS",
        "CONFERENCE",
        [
            "neurips",
            "nips",
            "advances in neural information processing systems",
            "neural information processing systems",
        ],
    ),
    "icml": (
        "ICML",
        "CONFERENCE",
        ["icml", "international conference on machine learning"],
    ),
    "iclr": (
        "ICLR",
        "CONFERENCE",
        ["iclr", "international conference on learning representations"],
    ),
    "cvpr": (
        "CVPR",
        "CONFERENCE",
        [
            "cvpr",
            "ieee/cvf conference on computer vision and pattern recognition",
            "computer vision and pattern recognition",
        ],
    ),
    "iccv": (
        "ICCV",
        "CONFERENCE",
        ["iccv", "ieee/cvf international conference on computer vision"],
    ),
    "eccv": ("ECCV", "CONFERENCE", ["eccv", "european conference on computer vision"]),
    "aaai": (
        "AAAI",
        "CONFERENCE",
        ["aaai", "aaai conference on artificial intelligence"],
    ),
    "ijcai": (
        "IJCAI",
        "CONFERENCE",
        ["ijcai", "international joint conference on artificial intelligence"],
    ),
    "acl": (
        "ACL",
        "CONFERENCE",
        ["acl", "annual meeting of the association for computational linguistics"],
    ),
    "emnlp": (
        "EMNLP",
        "CONFERENCE",
        ["emnlp", "empirical methods in natural language processing"],
    ),
    "naacl": (
        "NAACL",
        "CONFERENCE",
        [
            "naacl",
            "north american chapter of the association for computational linguistics",
        ],
    ),
    "aistats": (
        "AISTATS",
        "CONFERENCE",
        ["aistats", "artificial intelligence and statistics"],
    ),
    "uai": ("UAI", "CONFERENCE", ["uai", "uncertainty in artificial intelligence"]),
    "colt": ("COLT", "CONFERENCE", ["colt", "conference on learning theory"]),
    "kdd": ("KDD", "CONFERENCE", ["kdd", "knowledge discovery and data mining"]),
    "www": ("WWW", "CONFERENCE", ["www", "the web conference", "world wide web"]),
    "sigir": (
        "SIGIR",
        "CONFERENCE",
        ["sigir", "research and development in information retrieval"],
    ),
    "icra": (
        "ICRA",
        "CONFERENCE",
        ["icra", "ieee international conference on robotics and automation"],
    ),
    "iros": (
        "IROS",
        "CONFERENCE",
        ["iros", "ieee/rsj international conference on intelligent robots and systems"],
    ),
    "corl": ("CoRL", "CONFERENCE", ["corl", "conference on robot learning"]),
    # Journals
    "jmlr": ("JMLR", "JOURNAL", ["jmlr", "journal of machine learning research"]),
    "tmlr": ("TMLR", "JOURNAL", ["tmlr", "transactions on machine learning research"]),
    "nature": ("Nature", "JOURNAL", ["nature"]),
    "science": ("Science", "JOURNAL", ["science"]),
    "prl": ("PRL", "JOURNAL", ["prl", "physical review letters"]),
    "pre": ("PRE", "JOURNAL", ["pre", "physical review e"]),
    "prx": ("PRX", "JOURNAL", ["prx", "physical review x"]),
    "rmp": ("RMP", "JOURNAL", ["rmp", "reviews of modern physics"]),
    "pnas": (
        "PNAS",
        "JOURNAL",
        ["pnas", "proceedings of the national academy of sciences"],
    ),
    "tpami": (
        "TPAMI",
        "JOURNAL",
        ["tpami", "ieee transactions on pattern analysis and machine intelligence"],
    ),
    "neco": ("Neural Computation", "JOURNAL", ["neco", "neural computation"]),
    "tacl": (
        "TACL",
        "JOURNAL",
        ["tacl", "transactions of the association for computational linguistics"],
    ),
}

# Build reverse lookup: normalized alias -> venue slug
_VENUE_ALIAS_MAP: dict[str, str] = {}
for slug, (_, _, aliases) in VENUE_DATA.items():
    for alias in aliases:
        _VENUE_ALIAS_MAP[alias.lower()] = slug


def parse_folio_comment(content: str) -> dict[str, str | list[str]]:
    """
    Parse @COMMENT{folio: ...} blocks from raw file content.

    Returns dict with keys like 'subject', 'topics'.
    Topics are returned as a list (split by |).
    """
    result: dict[str, str | list[str]] = {}

    # Match @COMMENT{folio: ...} - case insensitive
    pattern = r"@COMMENT\{folio:\s*([^}]+)\}"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)

    if not match:
        return result

    # Parse key = value pairs
    folio_content = match.group(1)
    for line in folio_content.split("\n"):
        line = line.strip()
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip().lower()
            value = value.strip().rstrip(",")

            if key == "topics":
                # Split by | for multiple topics
                topics = [t.strip() for t in value.split("|")]
                result["topics"] = [t for t in topics if t]
            else:
                result[key] = value

    return result


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
    - subject: str | None (from file-level @COMMENT)
    - topics: list[str] (from file-level @COMMENT)
    - venue_slug: str | None (normalized from booktitle/journal)
    """
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode

    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            raw_content = f.read()
    except Exception as e:
        logger.error("Error reading %s: %s", filepath, e)
        return []

    # Parse file-level @COMMENT{folio: ...} metadata
    file_metadata = parse_folio_comment(raw_content)

    try:
        bib_database = bibtexparser.loads(raw_content, parser=parser)
    except Exception as e:
        logger.error("Error parsing %s: %s", filepath, e)
        return []

    entries = []
    for entry in bib_database.entries:
        try:
            parsed = parse_entry(entry, str(filepath), file_metadata)
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
    file_metadata: dict[str, str | list[str]] | None = None,
) -> dict | None:
    """Parse a single BibTeX entry into our schema."""
    entry_type_str = entry.get("ENTRYTYPE", "").lower()
    citation_key = entry.get("ID", "")

    if not citation_key:
        logger.debug("Skipping entry without ID in %s", source_file)
        return None

    file_metadata = file_metadata or {}

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

    # Extract venue from booktitle (conferences) or journal (articles)
    venue_slug: str | None = None
    booktitle = entry.get("booktitle", "")
    journal = entry.get("journal", "")

    if booktitle:
        venue_slug = normalize_venue(booktitle)
    elif journal:
        venue_slug = normalize_venue(journal)

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

    # Get file-level metadata
    subject = file_metadata.get("subject")
    topics = file_metadata.get("topics", [])
    if isinstance(subject, list):
        subject = subject[0] if subject else None
    if isinstance(topics, str):
        topics = [topics]

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
        # New metadata fields
        "subject": subject,
        "topics": topics,
        "venue_slug": venue_slug,
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
