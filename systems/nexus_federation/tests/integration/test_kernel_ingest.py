"""INTEGRATION tests: full kernel pipeline against real DAT.AI-shaped
reports, real evidence resolution, real SQLite persistence."""

from __future__ import annotations

from kernel import FederationKernel
from persistence.db import FederationStore
from tests.conftest import make_dat_ai_payload


def test_valid_report_is_accepted_and_registered(kernel: FederationKernel):
    result = kernel.ingest_report(make_dat_ai_payload())
    assert result.accepted is True
    assert result.registry_entry["institution_id"] == "dat_ai"
    assert result.registry_entry["maturity"] == "INTEGRATED"


def test_registry_state_is_granular_not_one_boolean(kernel: FederationKernel):
    result = kernel.ingest_report(make_dat_ai_payload())
    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["zoning_api"]["reported_lifecycle"] == "INTEGRATED"
    assert caps["valuation"]["reported_lifecycle"] == "NOT_COMMISSIONED"
    assert caps["zoning_api"]["reported_lifecycle"] != caps["valuation"]["reported_lifecycle"]


def test_evidence_is_actually_resolved_not_merely_stored(kernel: FederationKernel):
    result = kernel.ingest_report(make_dat_ai_payload())
    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["zoning_api"]["evidence_resolved"] is True
    assert caps["zoning_api"]["executive_state_class"] == "DERIVED"


def test_unresolvable_evidence_yields_unknown_executive_state(kernel: FederationKernel):
    payload = make_dat_ai_payload(zoning_evidence_refs=["nonexistent_file_xyz.md"])
    result = kernel.ingest_report(payload)
    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["zoning_api"]["evidence_resolved"] is False
    assert caps["zoning_api"]["executive_state_class"] == "UNKNOWN"
    assert result.evidence_resolution_failures >= 1


def test_report_log_persists_every_ingest_attempt(kernel: FederationKernel, store: FederationStore):
    kernel.ingest_report(make_dat_ai_payload(cycle_id="c1"))
    kernel.ingest_report(make_dat_ai_payload(cycle_id="c2"))
    assert store.count_reports(institution_id="dat_ai") == 2


def test_second_call_with_new_cycle_id_updates_registry(kernel: FederationKernel):
    kernel.ingest_report(make_dat_ai_payload(cycle_id="c1", zoning_lifecycle="TESTED"))
    result = kernel.ingest_report(make_dat_ai_payload(cycle_id="c2", zoning_lifecycle="INTEGRATED"))
    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["zoning_api"]["reported_lifecycle"] == "INTEGRATED"
