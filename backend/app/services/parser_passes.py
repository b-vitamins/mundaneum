"""
Registered parser passes for BibTeX normalization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.services.parser_pipeline import (
    EntryParseState,
    apply_file_metadata,
    normalize_authors,
    normalize_entry_type,
    normalize_file_path,
    normalize_title_and_year,
    normalize_venue,
    split_required_optional_fields,
)


@dataclass(frozen=True, slots=True)
class ParserPass:
    """One ordered transformation over entry parse state."""

    name: str
    apply: Callable[[EntryParseState], None]


def build_parser_passes(
    *,
    clean_latex_string: Callable[[str], str],
    parse_authors: Callable[[str], list[str]],
    resolve_venue: Callable[[str], str | None],
) -> tuple[ParserPass, ...]:
    """Build the default ordered parser pipeline."""
    return (
        ParserPass("entry_type", normalize_entry_type),
        ParserPass(
            "title_year",
            lambda state: normalize_title_and_year(
                state,
                clean_latex_string=clean_latex_string,
            ),
        ),
        ParserPass("file_path", normalize_file_path),
        ParserPass(
            "authors",
            lambda state: normalize_authors(
                state,
                parse_authors=parse_authors,
            ),
        ),
        ParserPass(
            "venue",
            lambda state: normalize_venue(
                state,
                resolve_venue=resolve_venue,
            ),
        ),
        ParserPass("fields", split_required_optional_fields),
        ParserPass("file_metadata", apply_file_metadata),
    )


def run_parser_passes(
    state: EntryParseState,
    passes: tuple[ParserPass, ...],
) -> None:
    """Run a registered parser pipeline over one entry."""
    for parser_pass in passes:
        parser_pass.apply(state)
