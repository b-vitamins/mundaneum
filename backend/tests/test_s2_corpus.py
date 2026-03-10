from app.services.s2_corpus_mappers import CorpusRowMapper
from app.services.s2_protocol import PaperRecord
from app.services.s2_source_registry import S2SourceRegistry


class NullSource:
    async def get_paper(self, s2_id: str):
        return None

    async def get_paper_by_corpus_id(self, corpus_id: int):
        return None

    async def get_references(self, s2_id: str, *, limit: int | None = None):
        return None

    async def get_citations(self, s2_id: str, *, limit: int | None = None):
        return None

    async def resolve_id(self, id_type: str, identifier: str):
        return None

    async def search(self, query: str, limit: int = 10):
        return None

    async def get_reference_ids(self, s2_id: str):
        return None


class PaperSource(NullSource):
    def __init__(self, paper: PaperRecord):
        self._paper = paper

    async def get_paper(self, s2_id: str):
        return self._paper


async def test_source_registry_falls_through_none():
    registry = S2SourceRegistry()
    registry.register("local", NullSource())
    registry.register("live", PaperSource(PaperRecord(s2_id="live", title="Live")))

    paper = await registry.chain().get_paper("missing")

    assert paper is not None
    assert paper.s2_id == "live"


def test_source_registry_tracks_names():
    registry = S2SourceRegistry()
    registry.register("local", NullSource())
    registry.register("live", NullSource())

    assert registry.names() == ("local", "live")


def test_corpus_row_mapper_enriches_local_rows():
    base = CorpusRowMapper.paper_from_row(
        ("Flexible Systems", 2024, "MIT Press", 12, 4, 2, True, None),
        corpus_id=7,
        s2_id="paper-7",
    )

    enriched = CorpusRowMapper.enrich_paper(
        base,
        abstract_row=("A book about flexible software.",),
        tldr_row=("Make change additive.",),
        author_rows=[("a1", "Sussman"), ("a2", "Hanson")],
    )

    assert enriched.s2_id == "paper-7"
    assert enriched.abstract == "A book about flexible software."
    assert enriched.tldr == "Make change additive."
    assert enriched.authors[0]["name"] == "Sussman"


def test_corpus_row_mapper_handles_live_api_shapes():
    paper = CorpusRowMapper.api_paper(
        {
            "paperId": "api-1",
            "title": "Propagators",
            "year": 2023,
            "venue": "ArXiv",
            "authors": [{"authorId": "a1", "name": "Ada"}],
            "tldr": {"text": "Composable systems."},
            "openAccessPdf": {"url": "https://example.com/paper.pdf"},
            "citationCount": 11,
            "referenceCount": 5,
            "influentialCitationCount": 3,
            "isOpenAccess": True,
            "fieldsOfStudy": [{"category": "Computer Science"}],
            "publicationTypes": ["Review"],
            "externalIds": {"DOI": "10.1/test"},
        }
    )

    assert paper.s2_id == "api-1"
    assert paper.tldr == "Composable systems."
    assert paper.open_access_pdf_url == "https://example.com/paper.pdf"
    assert paper.fields_of_study == ["Computer Science"]
