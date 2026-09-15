"""Institutional reporter (reporting/reporter.py) unit tests."""

from __future__ import annotations

from contracts.generic import CapabilityLifecycle, InstitutionalReport
from reporting.reporter import all_capability_statuses, build_current_report


def test_all_capabilities_present_and_named():
    caps = all_capability_statuses()
    names = {c.name for c in caps}
    assert "corpus_ingestion" in names
    assert "corpus_storage" in names
    assert "corpus_retrieval" in names
    assert "literature_review" in names


def test_real_capabilities_are_not_not_implemented():
    caps = {c.name: c for c in all_capability_statuses()}
    assert caps["corpus_ingestion"].lifecycle == CapabilityLifecycle.INTEGRATED
    assert caps["corpus_retrieval"].lifecycle == CapabilityLifecycle.TESTED


def test_unbuilt_capabilities_are_not_commissioned_never_fabricated():
    caps = {c.name: c for c in all_capability_statuses()}
    assert caps["literature_review"].lifecycle == CapabilityLifecycle.NOT_COMMISSIONED
    assert caps["citation_academic_metadata"].lifecycle == CapabilityLifecycle.NOT_COMMISSIONED
    assert caps["hypothesis_project_paper_generation"].lifecycle == CapabilityLifecycle.NOT_COMMISSIONED
    # None of these ever claim OPERATIONAL/EMPIRICALLY_VALIDATED:
    for cap in caps.values():
        assert cap.lifecycle not in (CapabilityLifecycle.OPERATIONAL, CapabilityLifecycle.EMPIRICALLY_VALIDATED)


def test_build_current_report_validates_against_generic_contract():
    report = build_current_report(mission_id="test-mission")
    assert isinstance(report, InstitutionalReport)
    assert report.institution == "librarian"
    # Round-trip through the real validator, exactly as NEXUS ingress does:
    from contracts.generic import validate_report

    revalidated = validate_report(report.model_dump(mode="json"))
    assert revalidated.institution == "librarian"


def test_report_never_self_declares_operational():
    report = build_current_report(mission_id="test-mission")
    assert report.operating_state.value != "OPERATIONAL"
