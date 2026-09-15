"""Synthesis/contradiction/research-gap tests -- clearly-labeled synthetic
fixtures with KNOWN ground truth for the keyword-marker heuristic."""

from __future__ import annotations

from academic.retrieval import AcademicSearchHit
from academic.synthesis import (
    ClaimSupportStatus,
    ResearchGapType,
    classify_claim_support,
    classify_research_gap,
)


def _hit(excerpt: str, source_id="test:x") -> AcademicSearchHit:
    return AcademicSearchHit(
        source_id=source_id, title="t", source_type="ACADEMIC_PREPRINT", doi="UNKNOWN",
        canonical_url="UNKNOWN", retraction_status="ACTIVE", matched_terms=("x",),
        match_count=1, excerpt=excerpt,
    )


def test_no_hits_is_insufficient_evidence():
    status, basis = classify_claim_support([])
    assert status == ClaimSupportStatus.INSUFFICIENT_EVIDENCE
    assert "no matching sources" in basis


def test_support_markers_only_yields_consensus():
    hits = [_hit("Our results support the hypothesis and confirm prior findings.")]
    status, _ = classify_claim_support(hits)
    assert status == ClaimSupportStatus.CONSENSUS


def test_contradiction_markers_only_yields_contradictory():
    hits = [_hit("However, our results are inconsistent with the prior model and fail to replicate it.")]
    status, _ = classify_claim_support(hits)
    assert status == ClaimSupportStatus.CONTRADICTORY


def test_both_markers_present_yields_mixed():
    hits = [
        _hit("Our results support this claim.", source_id="test:a"),
        _hit("However, this contradicts an earlier study.", source_id="test:b"),
    ]
    status, _ = classify_claim_support(hits)
    assert status == ClaimSupportStatus.MIXED


def test_neutral_hits_with_no_markers_yields_insufficient_evidence_not_fabricated_consensus():
    hits = [_hit("This paper describes a new dataset of aerial images collected in 2018.")]
    status, basis = classify_claim_support(hits)
    assert status == ClaimSupportStatus.INSUFFICIENT_EVIDENCE
    assert "NOT_COMMISSIONED" in basis


def test_gap_classification_corpus_empty():
    gap = classify_research_gap(hits=[], corpus_has_any_sources=False)
    assert gap.gap_type == ResearchGapType.CORPUS_GAP


def test_gap_classification_retrieval_failure_not_blanket_research_gap():
    """Mission section 19: 'no retrieved result' must not be silently
    relabeled a generic research gap -- it is specifically a
    RETRIEVAL_FAILURE (or CORPUS_GAP), never LITERATURE_GAP/
    OPEN_SCIENTIFIC_QUESTION, which require stronger evidence this
    mechanism cannot produce."""
    gap = classify_research_gap(hits=[], corpus_has_any_sources=True)
    assert gap.gap_type == ResearchGapType.RETRIEVAL_FAILURE
    assert gap.gap_type != ResearchGapType.LITERATURE_GAP
    assert gap.gap_type != ResearchGapType.OPEN_SCIENTIFIC_QUESTION


def test_no_gap_when_hits_exist():
    gap = classify_research_gap(hits=[_hit("x")], corpus_has_any_sources=True)
    assert gap is None
