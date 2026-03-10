"""
Pure graph-ranking and similarity helpers.
"""

from itertools import combinations

from app.services.graph_models import SimilarityEdge


def build_neighborhoods(
    edges: list[tuple[str, str, bool]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Build citers-of and refs-of maps from edge tuples."""
    citers_of: dict[str, set[str]] = {}
    refs_of: dict[str, set[str]] = {}

    for src, tgt, _ in edges:
        citers_of.setdefault(tgt, set()).add(src)
        refs_of.setdefault(src, set()).add(tgt)

    return citers_of, refs_of


def similarity_to_center(
    center_id: str,
    candidate_id: str,
    citers_of: dict[str, set[str]],
    refs_of: dict[str, set[str]],
) -> float:
    """Compute similarity using co-citation or bibliographic coupling Jaccard."""
    center_citers = citers_of.get(center_id, set())
    candidate_citers = citers_of.get(candidate_id, set())
    cocitation_union = len(center_citers | candidate_citers)
    cocitation = (
        len(center_citers & candidate_citers) / cocitation_union
        if cocitation_union > 0
        else 0.0
    )

    center_refs = refs_of.get(center_id, set())
    candidate_refs = refs_of.get(candidate_id, set())
    coupling_union = len(center_refs | candidate_refs)
    coupling = (
        len(center_refs & candidate_refs) / coupling_union
        if coupling_union > 0
        else 0.0
    )

    return max(cocitation, coupling)


def compute_similarity_edges(
    selected_ids: set[str],
    all_edges: list[tuple[str, str, bool]],
    min_weight: float = 0.03,
) -> list[SimilarityEdge]:
    """Compute similarity edges for the selected graph nodes."""
    citers_of, refs_of = build_neighborhoods(all_edges)
    similarity_edges: list[SimilarityEdge] = []

    for source, target in combinations(list(selected_ids), 2):
        weight = similarity_to_center(source, target, citers_of, refs_of)
        if weight >= min_weight:
            similarity_edges.append(
                SimilarityEdge(source=source, target=target, weight=weight)
            )

    similarity_edges.sort(key=lambda edge: edge.weight, reverse=True)
    return similarity_edges[:800]
