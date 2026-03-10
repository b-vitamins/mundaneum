"""
Search request and response models.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.models import EntryType


class SearchStatus(str, Enum):
    """Execution status for a search request."""

    OK = "ok"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class SearchSource(str, Enum):
    """Source that produced the search response."""

    MEILISEARCH = "meilisearch"
    DATABASE = "database"
    NONE = "none"


class SearchWarning(BaseModel):
    """Structured search degradation metadata."""

    code: str
    message: str


class SearchSortField(str, Enum):
    """Supported search ordering fields."""

    CREATED_AT = "created_at"
    YEAR = "year"
    TITLE = "title"


class SearchSortOrder(str, Enum):
    """Supported search ordering directions."""

    ASC = "asc"
    DESC = "desc"


class SearchSort(BaseModel):
    """Typed search ordering policy."""

    field: SearchSortField = SearchSortField.CREATED_AT
    order: SearchSortOrder = SearchSortOrder.DESC

    @classmethod
    def from_raw(cls, raw: str | None) -> "SearchSort":
        if not raw:
            return cls()

        field, _, order = raw.partition(":")
        normalized_field = (
            SearchSortField(field)
            if field in SearchSortField._value2member_map_
            else SearchSortField.CREATED_AT
        )
        normalized_order = (
            SearchSortOrder(order)
            if order in SearchSortOrder._value2member_map_
            else SearchSortOrder.DESC
        )
        return cls(field=normalized_field, order=normalized_order)

    @property
    def meilisearch_value(self) -> str:
        return f"{self.field.value}:{self.order.value}"


class SearchFilters(BaseModel):
    """Typed search filter set."""

    entry_type: EntryType | None = None
    year_from: int | None = None
    year_to: int | None = None
    has_pdf: bool | None = None
    read: bool | None = None

    @model_validator(mode="after")
    def validate_year_bounds(self) -> "SearchFilters":
        if (
            self.year_from is not None
            and self.year_to is not None
            and self.year_from > self.year_to
        ):
            raise ValueError("year_from must be less than or equal to year_to")
        return self


class SearchQuery(BaseModel):
    """Normalized search query and paging options."""

    query: str | None = None
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort: SearchSort = Field(default_factory=SearchSort)

    @property
    def normalized_query(self) -> str | None:
        if self.query is None:
            return None
        stripped = self.query.strip()
        return stripped or None


class SearchHitResponse(BaseModel):
    """Typed search hit payload."""

    id: str
    citation_key: str
    entry_type: str
    title: str
    year: int | None = None
    authors: list[str]
    venue: str | None = None
    abstract: str | None = None
    has_pdf: bool = False
    read: bool = False


class SearchResponse(BaseModel):
    """Typed search response with explicit degradation state."""

    status: SearchStatus
    source: SearchSource
    hits: list[SearchHitResponse]
    total: int
    processing_time_ms: int
    warnings: list[SearchWarning] = Field(default_factory=list)

    @classmethod
    def ok(
        cls,
        *,
        source: SearchSource,
        hits: list[SearchHitResponse],
        total: int,
        processing_time_ms: int,
    ) -> "SearchResponse":
        return cls(
            status=SearchStatus.OK,
            source=source,
            hits=hits,
            total=total,
            processing_time_ms=processing_time_ms,
        )

    @classmethod
    def partial(
        cls,
        *,
        source: SearchSource,
        hits: list[SearchHitResponse],
        total: int,
        processing_time_ms: int = 0,
        warnings: list[SearchWarning] | None = None,
    ) -> "SearchResponse":
        return cls(
            status=SearchStatus.PARTIAL,
            source=source,
            hits=hits,
            total=total,
            processing_time_ms=processing_time_ms,
            warnings=warnings or [],
        )

    @classmethod
    def unavailable(
        cls,
        *,
        warnings: list[SearchWarning] | None = None,
    ) -> "SearchResponse":
        return cls(
            status=SearchStatus.UNAVAILABLE,
            source=SearchSource.NONE,
            hits=[],
            total=0,
            processing_time_ms=0,
            warnings=warnings or [],
        )
