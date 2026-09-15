"""Citation graph: closed edge-type vocabulary + verification-gated edge
creation.

NEW module, NEXUS Librarian F4. Nodes are academic sources (by
`source_id`). Edges carry a REQUIRED `evidence` string — the mission's
explicit instruction is "only infer semantic relations such as
SUPPORTS/CONTRADICTS when there is evidence for the classification. Do
not derive them solely from citation existence" — enforced structurally
here: `AcademicStore.add_citation_edge()` raises if `evidence` is empty.

Honest current state: this mission's real source manifest
(`real_source_manifest.json`) was ingested from arXiv ABSTRACTS only —
reference lists were never extracted (out of scope this phase; extracting
and verifying real citation relationships between specific papers is
substantial additional work). Zero edges are populated from the real
manifest as a result. This module's mechanism (the schema, the
verification gate, the query API) is proven correct via
`tests/academic/test_citation_graph.py` using clearly-labeled synthetic
fixtures — never presented as claims about the real 22-source corpus.
See CITATION_GRAPH_SPEC.md LIMITATIONS.
"""

from __future__ import annotations

from enum import Enum

from academic.store import AcademicStore


class CitationEdgeType(str, Enum):
    CITES = "CITES"
    CITED_BY = "CITED_BY"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    EXTENDS = "EXTENDS"
    REPLICATES = "REPLICATES"
    CORRECTS = "CORRECTS"
    RETRACTS = "RETRACTS"


# Edge types that assert existence of a reference (structural), vs. edge
# types that assert a SEMANTIC relationship (require stronger evidence).
STRUCTURAL_EDGE_TYPES = frozenset({CitationEdgeType.CITES, CitationEdgeType.CITED_BY})
SEMANTIC_EDGE_TYPES = frozenset(CitationEdgeType) - STRUCTURAL_EDGE_TYPES


def add_edge(
    store: AcademicStore,
    *,
    source_from: str,
    source_to: str,
    edge_type: CitationEdgeType,
    evidence: str,
    verified: bool = False,
) -> bool:
    """Thin, typed wrapper over AcademicStore.add_citation_edge. Semantic
    edge types (SUPPORTS/CONTRADICTS/EXTENDS/REPLICATES/CORRECTS/RETRACTS)
    require `evidence` to name something more specific than mere
    co-occurrence in a citation list -- this is a documentation/discipline
    requirement (enforced by convention in the evidence string's content,
    since a generic 'this cites that' string is a valid, if weak, form of
    evidence and cannot be mechanically distinguished from a strong one at
    this schema level)."""
    return store.add_citation_edge(
        source_from=source_from,
        source_to=source_to,
        edge_type=edge_type.value,
        evidence=evidence,
        verified=verified,
    )


def get_edges(store: AcademicStore, source_id: str) -> list[dict]:
    return store.get_edges_for(source_id)
