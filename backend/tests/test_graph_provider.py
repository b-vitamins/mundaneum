from uuid import uuid4

import pytest

from app.models import Entry, EntryType
from app.services.graph import SQLAlchemyGraphProvider
from app.services.s2_protocol import EdgeRecord, PaperRecord


class FakeGraphSource:
    def __init__(self):
        self._papers = {
            "center": PaperRecord(
                s2_id="center",
                title="Center",
                citation_count=10,
                authors=[{"name": "Ada"}],
            ),
            "neighbor": PaperRecord(
                s2_id="neighbor",
                title="Neighbor",
                citation_count=5,
                authors=[{"name": "Grace"}],
            ),
            "shared": PaperRecord(
                s2_id="shared",
                title="Shared Reference",
                citation_count=20,
                authors=[{"name": "Katherine"}],
            ),
        }

    async def get_paper(self, s2_id: str):
        return self._papers.get(s2_id)

    async def get_paper_by_corpus_id(self, corpus_id: int):
        return None

    async def get_references(self, s2_id: str, *, limit: int | None = None):
        if s2_id == "center":
            return [
                EdgeRecord(citing_s2_id="center", cited_s2_id="neighbor"),
                EdgeRecord(citing_s2_id="center", cited_s2_id="shared"),
            ]
        if s2_id == "neighbor":
            return [EdgeRecord(citing_s2_id="neighbor", cited_s2_id="shared")]
        return []

    async def get_citations(self, s2_id: str, *, limit: int | None = None):
        if s2_id == "center":
            return [EdgeRecord(citing_s2_id="neighbor", cited_s2_id="center")]
        return []

    async def resolve_id(self, id_type: str, identifier: str):
        return None

    async def search(self, query: str, limit: int = 10):
        return []

    async def get_reference_ids(self, s2_id: str):
        refs = await self.get_references(s2_id)
        return {edge.cited_s2_id for edge in refs if edge.cited_s2_id}


@pytest.mark.asyncio
async def test_graph_provider_resolves_entry_s2_id(db_session):
    entry = Entry(
        title="Graph Paper",
        citation_key=f"graph_{uuid4().hex}",
        entry_type=EntryType.ARTICLE,
        source_file="graph.bib",
        s2_id="center",
    )
    db_session.add(entry)
    await db_session.commit()

    provider = SQLAlchemyGraphProvider(db_session, source=FakeGraphSource())
    assert await provider.resolve_entry_s2_id(str(entry.id)) == "center"


@pytest.mark.asyncio
async def test_graph_provider_builds_subgraph(db_session):
    provider = SQLAlchemyGraphProvider(db_session, source=FakeGraphSource())

    graph = await provider.get_subgraph("center", depth=2, max_nodes=10)

    assert graph.center_id == "center"
    assert {node.id for node in graph.nodes} >= {"center", "neighbor"}
    assert any(
        edge.source == "center" and edge.target == "neighbor" for edge in graph.edges
    )
