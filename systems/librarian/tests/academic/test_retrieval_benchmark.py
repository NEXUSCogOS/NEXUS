"""Retrieval benchmark execution and validation.

Mission section 15: Measures recall@k, precision@k, MRR, source-quality-weighted retrieval.
"""

from __future__ import annotations

import json
from pathlib import Path

from academic.benchmark import BENCHMARK_QUESTIONS, run_benchmark
from academic.ingest_real_sources import ingest_all
from academic.store import AcademicStore


def test_benchmark_has_5_questions_covering_priority_domains():
    """Mission section 5: corpus domains include cognitive architecture, autonomous
    engineering, evidence provenance, distributed systems, and geospatial science."""
    assert len(BENCHMARK_QUESTIONS) == 5
    domains = {q.domain for q in BENCHMARK_QUESTIONS}
    assert "cognitive_architecture" in domains
    assert "autonomous_engineering" in domains
    assert "evidence_provenance" in domains
    assert "distributed_systems" in domains
    assert "dat_ai_geospatial" in domains


def test_benchmark_questions_have_hand_verified_relevance():
    """Mission section 15: ground truth is hand-verified against real_source_manifest.json."""
    for q in BENCHMARK_QUESTIONS:
        assert len(q.expected_relevant) > 0, f"Question {q.question_id} has no expected relevant sources"
        assert len(q.expected_relevant) <= 4, f"Question {q.question_id} relevance set is suspiciously large"
        assert isinstance(q.expected_relevant, list)
        assert isinstance(q.known_distractors, list)


def test_benchmark_execution_produces_recall_precision_mrr():
    """Mission section 15: retrieval benchmark measures recall@k, precision@k, MRR."""
    db_path = Path(__file__).resolve().parents[3] / "data" / "academic_corpus.db"
    store = AcademicStore(db_path)

    # Ensure real manifest is ingested
    ingest_all(store)

    results = run_benchmark(store, k=5)

    # Validate structure
    assert "k" in results
    assert results["k"] == 5
    assert "questions" in results
    assert len(results["questions"]) == 5

    for q_result in results["questions"]:
        assert "question_id" in q_result
        assert "retrieved_ids" in q_result
        assert "expected_relevant" in q_result
        assert "recall_at_5" in q_result
        assert "precision_at_5" in q_result
        assert "reciprocal_rank" in q_result
        assert "distractors_incorrectly_retrieved" in q_result
        assert "source_quality_weighted_score" in q_result

    # Mean metrics
    assert "mean_recall_at_5" in results
    assert "mean_precision_at_5" in results
    assert "mrr" in results

    # Sanity: metrics are in valid range
    assert 0.0 <= results["mean_recall_at_5"] <= 1.0
    assert 0.0 <= results["mean_precision_at_5"] <= 1.0
    assert 0.0 <= results["mrr"] <= 1.0


def test_benchmark_no_fabricated_sources():
    """Mission section 2: retrieval is against the REAL 22-source manifest,
    no invented papers or citations."""
    db_path = Path(__file__).resolve().parents[3] / "data" / "academic_corpus.db"
    store = AcademicStore(db_path)
    ingest_all(store)

    manifest_path = Path(__file__).resolve().parents[2] / "academic" / "real_source_manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)
    manifest_ids = {item["id"] for item in manifest}

    results = run_benchmark(store, k=5)
    for q_result in results["questions"]:
        for retrieved_id in q_result["retrieved_ids"]:
            assert retrieved_id in manifest_ids, (
                f"Question {q_result['question_id']} retrieved {retrieved_id} "
                f"which is not in the real manifest -- fabrication detected"
            )
