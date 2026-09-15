"""Integration tests for institutional/reporter.py against real component
checks (live database/PostGIS) and the real model checkpoint.

Marked `integration`: requires a live PostGIS database (see
DATAI_CANONICAL_TEST_BASELINE.md for the disposable-instance pattern).
"""

from __future__ import annotations

import pytest

from institutional.contract import CapabilityLifecycle, OperatingState
from institutional.reporter import (
    _component_evidence,
    _satellite_acquisition_capability,
    _satellite_classification_capability,
    _valuation_capability,
    _zoning_api_capability,
    all_capability_statuses,
    build_current_report,
)

pytestmark = pytest.mark.integration


def test_component_evidence_reflects_real_healthy_database(db_engine):
    evidence = _component_evidence()
    assert evidence.database == "healthy"
    assert evidence.postgis == "healthy"


def test_zoning_api_capability_is_integrated_when_db_healthy(db_engine):
    evidence = _component_evidence()
    status = _zoning_api_capability(evidence)
    assert status.lifecycle == CapabilityLifecycle.INTEGRATED
    assert status.evidence_refs


def test_satellite_classification_never_reports_empirically_validated_for_the_real_untrained_checkpoint():
    status = _satellite_classification_capability()
    if status.lifecycle == CapabilityLifecycle.NOT_IMPLEMENTED:
        pytest.skip("checkpoint file not present in this environment")
    assert status.lifecycle == CapabilityLifecycle.IMPLEMENTED
    assert status.lifecycle not in (
        CapabilityLifecycle.EMPIRICALLY_VALIDATED,
        CapabilityLifecycle.OPERATIONAL,
    )
    assert status.confidence.value == 0.0
    assert "untrained" in status.confidence.basis.lower() or "ImageNet" in status.confidence.basis


def test_satellite_acquisition_reports_external_dependency_unavailable_when_no_credentials():
    status = _satellite_acquisition_capability()
    # Per Phase A+B, credentials are confirmed absent from this estate.
    assert status.lifecycle == CapabilityLifecycle.EXTERNAL_DEPENDENCY_UNAVAILABLE
    assert "CDSE" in status.detail


def test_valuation_always_reports_not_commissioned():
    status = _valuation_capability()
    assert status.lifecycle == CapabilityLifecycle.NOT_COMMISSIONED
    assert status.lifecycle != CapabilityLifecycle.OPERATIONAL


def test_all_capability_statuses_returns_six_capabilities(db_engine):
    statuses = all_capability_statuses()
    names = {s.name for s in statuses}
    assert names == {
        "zoning_api",
        "model_registry",
        "promotion_gate",
        "satellite_classification",
        "satellite_acquisition",
        "valuation",
    }


def test_build_current_report_produces_a_valid_report_with_real_evidence(db_engine):
    report = build_current_report(mission_id="integration-test")
    assert report.institution == "dat_ai"
    assert report.evidence_refs  # populated from real capability checks
    assert any("valuation" in f and "NOT_COMMISSIONED" in f for f in report.findings)


def test_operating_state_not_dragged_down_by_untrained_model_or_uncommissioned_valuation(db_engine):
    """End-to-end proof of the core hardening requirement, via the real
    reporter rather than a synthetic fixture."""
    report = build_current_report(mission_id="integration-test")
    # Database/postgis/migrations are healthy in this test's disposable
    # instance, so the institution-level state must reflect the zoning_api
    # capability (INTEGRATED), not be dragged down to DEGRADED/UNAVAILABLE
    # by satellite_classification (IMPLEMENTED, untrained) or valuation
    # (NOT_COMMISSIONED).
    assert report.operating_state == OperatingState.INTEGRATED


def test_report_never_self_reports_operational(db_engine):
    report = build_current_report(mission_id="integration-test")
    assert report.operating_state != OperatingState.OPERATIONAL
    for status in report.capability_statuses:
        assert status.lifecycle != CapabilityLifecycle.OPERATIONAL
