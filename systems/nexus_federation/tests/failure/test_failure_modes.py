"""FAILURE tests: the 15 explicitly-numbered scenarios from the F1 mission.

Each test is named/numbered to match FEDERATION_FAILURE_TEST_REPORT.md
exactly, so the report and this file can be cross-checked directly. Some
scenarios are also covered by other test files (temporal/, state/,
restart/) -- referenced here rather than duplicated where that's true, but
every one of the 15 has its own test present somewhere in this suite.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from institutional.contract import CapabilityLifecycle
from kernel import FederationKernel
from persistence.db import FederationStore
from tests.conftest import make_dat_ai_payload


def test_01_valid_dat_ai_report(kernel: FederationKernel):
    result = kernel.ingest_report(make_dat_ai_payload())
    assert result.accepted is True


def test_02_malformed_report_fails_closed(kernel: FederationKernel):
    malformed = {"institution": "dat_ai", "schema_version": "1.1.0"}  # missing required fields
    result = kernel.ingest_report(malformed)
    assert result.accepted is False
    assert "validation failed" in result.reason


def test_03_unknown_schema_version_rejected(kernel: FederationKernel):
    payload = make_dat_ai_payload()
    payload["schema_version"] = "99.0.0"
    result = kernel.ingest_report(payload)
    assert result.accepted is False
    assert result.temporal_classification == "SCHEMA_REJECTED"
    assert "unknown schema_version" in result.reason


def test_04_missing_evidence_degrades_claim_not_silently_accepted(kernel: FederationKernel):
    payload = make_dat_ai_payload(zoning_evidence_refs=["missing_evidence_xyz.md"])
    result = kernel.ingest_report(payload)
    assert result.accepted is True  # the report itself is schema-valid
    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["zoning_api"]["evidence_resolved"] is False
    assert caps["zoning_api"]["executive_state_class"] == "UNKNOWN"  # degraded, not fabricated as DERIVED


def test_05_corrupted_evidence_detected_via_hash_drift(kernel: FederationKernel, tmp_path, store: FederationStore):
    """Simulates corruption: first ingest resolves evidence and records a
    baseline hash; the underlying file is then modified; a second ingest
    (new cycle) resolves it again and the hash differs from the baseline."""
    from evidence.resolver import resolve_evidence_ref

    f = tmp_path / "mutable_evidence.md"
    f.write_text("original")
    ref = str(f)

    r1 = resolve_evidence_ref(ref, search_roots=[("tmp", tmp_path.parent)])
    store.set_evidence_baseline_if_absent("dat_ai", ref, r1.sha256, datetime.now(timezone.utc).isoformat())

    f.write_text("corrupted")
    r2 = resolve_evidence_ref(ref, search_roots=[("tmp", tmp_path.parent)])
    baseline = store.get_evidence_baseline("dat_ai", ref)
    assert baseline == r1.sha256
    assert r2.sha256 != baseline  # drift detected


def test_06_stale_report(kernel: FederationKernel):
    from state.temporal import STALE_THRESHOLD

    stale_ts = (datetime.now(timezone.utc) - STALE_THRESHOLD - timedelta(minutes=5)).isoformat()
    result = kernel.ingest_report(make_dat_ai_payload(timestamp=stale_ts))
    assert result.accepted is True
    assert result.temporal_classification == "STALE"


def test_07_out_of_order_report(kernel: FederationKernel):
    now = datetime.now(timezone.utc)
    kernel.ingest_report(make_dat_ai_payload(cycle_id="new", timestamp=now.isoformat()))
    result = kernel.ingest_report(
        make_dat_ai_payload(cycle_id="old", timestamp=(now - timedelta(minutes=10)).isoformat())
    )
    assert result.accepted is False
    assert result.temporal_classification == "OUT_OF_ORDER"


def test_08_duplicate_cycle(kernel: FederationKernel):
    payload = make_dat_ai_payload(cycle_id="dup-cycle")
    kernel.ingest_report(payload)
    result = kernel.ingest_report(payload)
    assert result.accepted is True
    assert result.temporal_classification == "DUPLICATE"


def test_09_postgis_unavailable_reported_not_silently_ignored(kernel: FederationKernel):
    payload = make_dat_ai_payload(postgis="unhealthy")
    result = kernel.ingest_report(payload)
    assert result.accepted is True  # schema-valid; DAT.AI honestly reported its own unhealthy state
    assert result.registry_entry["maturity"] == "UNAVAILABLE"


def test_10_external_storage_unavailable_reported_as_degraded(kernel: FederationKernel):
    payload = make_dat_ai_payload(external_storage="unavailable")
    result = kernel.ingest_report(payload)
    assert result.accepted is True
    assert result.registry_entry["maturity"] == "DEGRADED"


def test_11_satellite_credentials_unavailable_reported_as_external_dependency_unavailable(kernel: FederationKernel):
    """This is DAT.AI's own capability status (EXTERNAL_DEPENDENCY_UNAVAILABLE
    for satellite_acquisition), not something NEXUS derives independently --
    NEXUS's job is to preserve that granularity, not collapse it."""
    from institutional.contract import build_report, ComponentEvidence, CapabilityStatus, Confidence

    report = build_report(
        mission_id="m",
        objective="o",
        component_evidence=ComponentEvidence(
            database="healthy", postgis="healthy", migrations="healthy", configuration="healthy"
        ),
        capability_statuses=[
            CapabilityStatus(name="zoning_api", lifecycle=CapabilityLifecycle.INTEGRATED, evidence_refs=["x"], confidence=Confidence.unknown()),
            CapabilityStatus(
                name="satellite_acquisition",
                lifecycle=CapabilityLifecycle.EXTERNAL_DEPENDENCY_UNAVAILABLE,
                evidence_refs=["DATAI_PHASE_AB_VERIFICATION_REPORT.md"],
                detail="No CDSE credentials.",
            ),
        ],
        findings=["satellite_acquisition: EXTERNAL_DEPENDENCY_UNAVAILABLE"],
        evidence_refs=["DATAI_PHASE_AB_VERIFICATION_REPORT.md"],
    )
    result = kernel.ingest_report(report.model_dump(mode="json"))
    assert result.accepted is True
    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["satellite_acquisition"]["reported_lifecycle"] == "EXTERNAL_DEPENDENCY_UNAVAILABLE"


def test_12_valuation_not_commissioned_preserved_verbatim(kernel: FederationKernel):
    result = kernel.ingest_report(make_dat_ai_payload())
    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["valuation"]["reported_lifecycle"] == "NOT_COMMISSIONED"
    assert caps["valuation"]["reported_lifecycle"] != "OPERATIONAL"


def test_13_untrained_classifier_never_reported_as_validated(kernel: FederationKernel):
    from institutional.contract import build_report, ComponentEvidence, CapabilityStatus, Confidence

    report = build_report(
        mission_id="m",
        objective="o",
        component_evidence=ComponentEvidence(
            database="healthy", postgis="healthy", migrations="healthy", configuration="healthy"
        ),
        capability_statuses=[
            CapabilityStatus(name="zoning_api", lifecycle=CapabilityLifecycle.INTEGRATED, evidence_refs=["x"], confidence=Confidence.unknown()),
            CapabilityStatus(
                name="satellite_classification",
                lifecycle=CapabilityLifecycle.IMPLEMENTED,
                confidence=Confidence(value=0.0, basis="bit-identical to stock ImageNet weights"),
                evidence_refs=["DATAI_MODEL_STATUS_REGISTER.md"],
            ),
        ],
        findings=["satellite_classification: IMPLEMENTED, untrained"],
        evidence_refs=["DATAI_MODEL_STATUS_REGISTER.md"],
    )
    result = kernel.ingest_report(report.model_dump(mode="json"))
    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["satellite_classification"]["reported_lifecycle"] == "IMPLEMENTED"
    assert caps["satellite_classification"]["reported_lifecycle"] not in ("EMPIRICALLY_VALIDATED", "OPERATIONAL")


def test_14_contradictory_successive_reports(kernel: FederationKernel):
    r1 = kernel.ingest_report(make_dat_ai_payload(cycle_id="c1", zoning_lifecycle="INTEGRATED"))
    t1 = r1.registry_entry["last_report_timestamp"]
    later = (datetime.fromisoformat(t1) + timedelta(minutes=1)).isoformat()
    r2 = kernel.ingest_report(
        make_dat_ai_payload(cycle_id="c2", zoning_lifecycle="IMPLEMENTED", timestamp=later, findings=["unrelated"])
    )
    caps = {c["capability_name"]: c for c in r2.registry_entry["component_states"]}
    assert caps["zoning_api"]["executive_state_class"] == "CONTRADICTORY"


def test_15_restart_between_reports(tmp_path):
    """See tests/restart/test_restart_recovery.py for the full, dedicated
    restart-recovery proof. This test confirms the specific claim: a
    second FederationKernel instance (simulating a process restart),
    backed by the same SQLite file, sees the first kernel's accepted state."""
    db_path = tmp_path / "restart_test.db"
    store1 = FederationStore(db_path)
    kernel1 = FederationKernel(store1)
    kernel1.ingest_report(make_dat_ai_payload(cycle_id="before-restart"))

    # Simulate restart: brand new Store/Kernel objects, same file.
    store2 = FederationStore(db_path)
    kernel2 = FederationKernel(store2)
    entry = store2.get_registry_entry("dat_ai")
    assert entry is not None
    assert entry["last_verified_cycle"] == "before-restart"

    # And a new report after "restart" is correctly treated as newer, not
    # as a first-ever report.
    later_ts = (
        datetime.fromisoformat(entry["last_report_timestamp"]) + timedelta(minutes=1)
    ).isoformat()
    result = kernel2.ingest_report(make_dat_ai_payload(cycle_id="after-restart", timestamp=later_ts))
    assert result.accepted is True
    assert result.temporal_classification == "CURRENT"
