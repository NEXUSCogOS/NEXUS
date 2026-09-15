"""Bounded ACADEMIC research-mission executor.

NEW module, NEXUS Librarian F4. Mirrors `runtime/research_executor.py`'s
honesty discipline (real retrieval, real evidence, explicit
INSUFFICIENT_EVIDENCE, never fabricated synthesis) but operates against
the SEPARATE academic corpus and adds the bounded synthesis workflow
(retrieval -> support classification -> gap classification ->
InstitutionalReport), per mission section 16/24.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from academic.retrieval import search as academic_search
from academic.store import AcademicStore
from academic.synthesis import (
    ClaimSupportStatus,
    ResearchGap,
    SynthesisFinding,
    SynthesisResult,
    classify_claim_support,
    classify_research_gap,
)
from contracts.generic import (
    CapabilityLifecycle,
    CapabilityStatus,
    Confidence,
    InstitutionalReport,
    OperatingState,
    build_report,
)

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def run_bounded_synthesis(
    *, research_question: str, query_terms: str, data_dir: Path | str, min_matched_terms: int = 2
) -> SynthesisResult:
    data_dir = Path(data_dir)
    store = AcademicStore(data_dir / "academic_corpus.db")

    hits = academic_search(store, query_terms, min_matched_terms=min_matched_terms)
    corpus_has_any_sources = store.count_sources() > 0

    gaps: list[ResearchGap] = []
    findings: list[SynthesisFinding] = []

    gap = classify_research_gap(hits=hits, corpus_has_any_sources=corpus_has_any_sources)
    if gap:
        gaps.append(gap)
    else:
        status, basis = classify_claim_support(hits)
        findings.append(
            SynthesisFinding(
                claim=research_question,
                evidence_refs=[h.source_id for h in hits],
                support_status=status,
                basis_for_status=basis,
            )
        )

    limitations = [
        "Support/contradiction classification (when reported) is a disclosed keyword-marker "
        "heuristic, NOT semantic entailment -- see academic/synthesis.py module docstring.",
        "Citation graph relationships between these sources were not extracted or verified "
        "this mission (zero real citation edges exist) -- see CITATION_GRAPH_SPEC.md.",
        "Peer-review status of all sources is UNVERIFIED (arXiv preprints; DOI presence in "
        "metadata was not independently confirmed to resolve to a peer-reviewed venue).",
    ]

    return SynthesisResult(
        research_question=research_question,
        findings=findings,
        gaps=gaps,
        hypotheses=[],  # no hypothesis generation performed this mission -- NOT_COMMISSIONED, see LIBRARIAN_LIMITATIONS.md
        limitations=limitations,
    )


def execute_academic_research_mission(
    *,
    mission_id: str,
    objective: str,
    research_question: str,
    query_terms: str,
    data_dir: Path | str = DEFAULT_DATA_DIR,
    cycle_id: Optional[str] = None,
) -> InstitutionalReport:
    result = run_bounded_synthesis(research_question=research_question, query_terms=query_terms, data_dir=data_dir)

    retrieval_capability = CapabilityStatus(
        name="academic_corpus_retrieval",
        lifecycle=CapabilityLifecycle.TESTED,
        confidence=Confidence(value=1.0, basis="lexical search executed against the real, separated academic corpus this cycle"),
        evidence_refs=["ACADEMIC_CORPUS_AUDIT.md"],
        detail=f"research_question={research_question!r}",
    )

    if result.gaps:
        gap = result.gaps[0]
        findings_text = [
            f"{gap.gap_type.value}: {gap.detail}",
        ]
        evidence_refs = ["ACADEMIC_CORPUS_AUDIT.md"]
        provenance_refs: list[str] = []
    else:
        finding = result.findings[0]
        findings_text = [
            f"support_status={finding.support_status.value} for claim {finding.claim!r} -- {finding.basis_for_status}"
        ]
        evidence_refs = finding.evidence_refs or ["ACADEMIC_CORPUS_AUDIT.md"]
        provenance_refs = [f"academic_source_id={sid}" for sid in finding.evidence_refs]

    return build_report(
        institution="librarian",
        mission_id=mission_id,
        objective=objective,
        operating_state=OperatingState.TESTED,
        capability_statuses=[retrieval_capability],
        findings=findings_text,
        evidence_refs=evidence_refs,
        provenance_refs=provenance_refs,
        limitations=result.limitations,
        cycle_id=cycle_id,
    )
