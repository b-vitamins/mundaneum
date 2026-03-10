"""
Typed value objects layered over JSON-backed model fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import BaseModel


@dataclass(frozen=True)
class EntryMetadata:
    """Typed accessors for Entry required/optional BibTeX fields."""

    required_fields: Mapping[str, Any]
    optional_fields: Mapping[str, Any]

    def get(self, *names: str) -> str | None:
        for fields in (self.required_fields, self.optional_fields):
            for name in names:
                value = fields.get(name) or fields.get(name.upper()) or fields.get(name.lower())
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @property
    def abstract(self) -> str | None:
        value = self.optional_fields.get("abstract")
        return value if isinstance(value, str) and value else None

    @property
    def venue_name(self) -> str | None:
        return self.get("journal", "booktitle")

    def dump_required(self) -> dict:
        return dict(self.required_fields)

    def dump_optional(self) -> dict:
        return dict(self.optional_fields)


class S2TLDRData(BaseModel):
    model: str | None = None
    text: str | None = None


class OpenAccessPDFData(BaseModel):
    url: str | None = None
    status: str | None = None
