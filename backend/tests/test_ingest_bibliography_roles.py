from app.models import Entry, EntryType, Topic, Venue, VenueCategory
from app.services.ingest_entities import (
    IngestBatchContext,
    apply_entry_fields,
    sync_topic_links,
)


def _entry_data(
    *,
    source_file: str,
    source_role: str,
    title: str,
    topics: list[str] | None = None,
    venue_slug: str | None = None,
) -> dict:
    return {
        "citation_key": "smith2024",
        "entry_type": EntryType.ARTICLE,
        "title": title,
        "year": 2024,
        "file_path": None,
        "authors": ["Alice Smith", "Bob Jones"],
        "required_fields": {},
        "optional_fields": {},
        "source_file": source_file,
        "source_role": source_role,
        "subject": None,
        "topics": topics or [],
        "venue_slug": venue_slug,
    }


def test_curated_entries_enrich_without_overwriting_canonical_fields():
    context = IngestBatchContext(
        venues_by_slug={
            "iclr": Venue(
                slug="iclr",
                name="ICLR",
                category=VenueCategory.CONFERENCE,
                aliases=["ICLR"],
            )
        },
        topics_by_slug={
            "transformers": Topic(slug="transformers", name="Transformers"),
            "attention": Topic(slug="attention", name="Attention"),
        },
    )
    entry = Entry(
        citation_key="smith2024",
        entry_type=EntryType.ARTICLE,
        title="Initial",
        source_file="seed.bib",
    )

    first_curated = _entry_data(
        source_file="collections/transformers.bib",
        source_role="curated",
        title="Curated Title",
        topics=["transformers"],
    )
    canonical = _entry_data(
        source_file="conferences/iclr/2024.bib",
        source_role="canonical",
        title="Canonical Title",
        venue_slug="iclr",
    )
    second_curated = _entry_data(
        source_file="collections/attention.bib",
        source_role="curated",
        title="Second Curated Title",
        topics=["attention"],
    )

    apply_entry_fields(entry, first_curated, context, created=True)
    sync_topic_links(entry, first_curated, context, created=True)

    apply_entry_fields(entry, canonical, context, created=False)
    sync_topic_links(entry, canonical, context, created=False)

    apply_entry_fields(entry, second_curated, context, created=False)
    sync_topic_links(entry, second_curated, context, created=False)

    assert entry.title == "Canonical Title"
    assert entry.source_file == "conferences/iclr/2024.bib"
    assert entry.venue is not None
    assert entry.venue.slug == "iclr"
    assert {entry_topic.topic.slug for entry_topic in entry.topics} == {
        "attention",
        "transformers",
    }
