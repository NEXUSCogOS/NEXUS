"""Citation graph tests -- against clearly-labeled SYNTHETIC fixtures with
known ground truth (never presented as claims about the real corpus)."""

from __future__ import annotations

import pytest

from academic.citation_graph import CitationEdgeType, add_edge, get_edges
from academic.store import AcademicStore


@pytest.fixture
def store(tmp_path):
    return AcademicStore(tmp_path / "citation_test.db")


def _seed_two_sources(store):
    store.upsert_source({
        "source_id": "test:paper_a", "title": "Synthetic Paper A", "authors": ["A"],
        "publication_date": "2020", "journal_or_venue": "UNKNOWN", "publisher": "UNKNOWN",
        "doi": "UNKNOWN", "external_identifiers": {"test": "a"}, "canonical_url": "UNKNOWN",
        "source_type": "ACADEMIC_PREPRINT", "peer_review_status": "UNVERIFIED",
        "retrieval_timestamp": "2020", "content_hash": "x", "license": "UNKNOWN",
        "language": "en", "version": "UNKNOWN", "retraction_status": "ACTIVE",
        "correction_status": "NONE", "ingestion_method": "test", "verification_status": "PARTIAL",
        "retrievable_text": "synthetic text A",
    })
    store.upsert_source({
        "source_id": "test:paper_b", "title": "Synthetic Paper B", "authors": ["B"],
        "publication_date": "2021", "journal_or_venue": "UNKNOWN", "publisher": "UNKNOWN",
        "doi": "UNKNOWN", "external_identifiers": {"test": "b"}, "canonical_url": "UNKNOWN",
        "source_type": "ACADEMIC_PREPRINT", "peer_review_status": "UNVERIFIED",
        "retrieval_timestamp": "2021", "content_hash": "y", "license": "UNKNOWN",
        "language": "en", "version": "UNKNOWN", "retraction_status": "ACTIVE",
        "correction_status": "NONE", "ingestion_method": "test", "verification_status": "PARTIAL",
        "retrievable_text": "synthetic text B",
    })


def test_edge_requires_nonempty_evidence(store):
    _seed_two_sources(store)
    with pytest.raises(ValueError):
        add_edge(store, source_from="test:paper_b", source_to="test:paper_a", edge_type=CitationEdgeType.CITES, evidence="")


def test_edge_created_with_real_evidence_string(store):
    _seed_two_sources(store)
    inserted = add_edge(
        store, source_from="test:paper_b", source_to="test:paper_a", edge_type=CitationEdgeType.CITES,
        evidence="paper B's reference list (synthetic fixture) lists paper A",
    )
    assert inserted is True
    edges = get_edges(store, "test:paper_a")
    assert len(edges) == 1
    assert edges[0]["edge_type"] == "CITES"


def test_duplicate_edge_not_created_twice(store):
    _seed_two_sources(store)
    add_edge(store, source_from="test:paper_b", source_to="test:paper_a", edge_type=CitationEdgeType.CITES, evidence="e1")
    second = add_edge(store, source_from="test:paper_b", source_to="test:paper_a", edge_type=CitationEdgeType.CITES, evidence="e2")
    assert second is False
    assert store.count_edges() == 1


def test_semantic_edge_type_requires_evidence_same_as_structural(store):
    """SUPPORTS/CONTRADICTS are not exempted from the evidence requirement."""
    _seed_two_sources(store)
    with pytest.raises(ValueError):
        add_edge(store, source_from="test:paper_a", source_to="test:paper_b", edge_type=CitationEdgeType.CONTRADICTS, evidence="")


def test_real_corpus_has_zero_unverified_citation_edges_this_mission():
    """Honest state check: the real ingested corpus has NO citation edges
    populated, because reference-list extraction was not performed this
    mission (see academic/citation_graph.py module docstring)."""
    from academic.ingest_real_sources import ingest_all

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        real_store = AcademicStore(f"{d}/academic_corpus.db")
        ingest_all(real_store)
        assert real_store.count_edges() == 0
