"""Bounded research-mission execution tests (runtime/research_executor.py).

Proves the mission's explicit requirement: "If evidence is insufficient,
Librarian must explicitly report INSUFFICIENT_EVIDENCE. That is a valid
successful scientific outcome."
"""

from __future__ import annotations

from runtime.research_executor import INSUFFICIENT_EVIDENCE, execute_research_mission


def test_domain_irrelevant_query_against_real_corpus_returns_insufficient_evidence(real_data_dir):
    """A genuinely unrelated, highly specific query against the real,
    non-academic corpus (see LIBRARIAN_CORPUS_AUDIT.md) must honestly
    report insufficient evidence -- not a fabricated finding."""
    report = execute_research_mission(
        mission_id="m1",
        objective="test",
        query="quantum chromodynamics lattice gauge theory renormalization",
        data_dir=real_data_dir,
    )
    assert len(report.findings) == 1
    assert INSUFFICIENT_EVIDENCE in report.findings[0]
    assert report.evidence_refs == ["LIBRARIAN_CORPUS_AUDIT.md"]


def test_real_self_referential_query_returns_real_findings(real_data_dir):
    """A query matching real content actually present in the corpus
    returns real, evidenced findings -- literal excerpts, not synthesis."""
    report = execute_research_mission(
        mission_id="m2",
        objective="test",
        query="ingestion provenance dedup chunk",
        data_dir=real_data_dir,
    )
    assert len(report.findings) >= 1
    assert INSUFFICIENT_EVIDENCE not in report.findings[0]
    assert "excerpt" in report.findings[0].lower() or "matched terms" in report.findings[0].lower()
    assert len(report.evidence_refs) == len(report.findings)


def test_findings_require_evidence_refs_enforced_by_generic_contract(real_data_dir):
    """The generic federation contract's own validator (findings require
    evidence_refs) is exercised here, not bypassed."""
    report = execute_research_mission(
        mission_id="m3", objective="test", query="ingestion provenance dedup chunk", data_dir=real_data_dir
    )
    assert report.findings  # has findings
    assert report.evidence_refs  # contract validator would have rejected otherwise


def test_report_never_claims_operational(real_data_dir):
    report = execute_research_mission(
        mission_id="m4", objective="test", query="anything", data_dir=real_data_dir
    )
    assert report.operating_state.value != "OPERATIONAL"
