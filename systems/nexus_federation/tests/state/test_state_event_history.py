"""Executive state event history tests: append-only, sufficient to
reconstruct capability state at cycle N, cycle N+1, and why it changed --
independent of and in addition to the materialized 'current state' in
institution_registry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kernel import FederationKernel
from persistence.db import FederationStore
from tests.conftest import make_dat_ai_payload


def test_first_ingest_produces_one_event_per_capability(kernel: FederationKernel, store: FederationStore):
    kernel.ingest_report(make_dat_ai_payload(cycle_id="c1"))
    events = store.get_state_events("dat_ai", "zoning_api")
    assert len(events) == 1
    assert events[0]["cycle_id"] == "c1"
    assert events[0]["prior_lifecycle"] is None  # first sighting -- no prior


def test_second_ingest_reconstructs_n_and_n_plus_1(kernel: FederationKernel, store: FederationStore):
    now = datetime.now(timezone.utc)
    kernel.ingest_report(make_dat_ai_payload(cycle_id="c1", zoning_lifecycle="TESTED", timestamp=now.isoformat()))
    later = (now + timedelta(minutes=1)).isoformat()
    kernel.ingest_report(
        make_dat_ai_payload(cycle_id="c2", zoning_lifecycle="INTEGRATED", timestamp=later, findings=["zoning_api: advanced"])
    )

    events = store.get_state_events("dat_ai", "zoning_api")
    assert len(events) == 2
    # Cycle N: what NEXUS believed at c1
    assert events[0]["cycle_id"] == "c1"
    assert events[0]["new_lifecycle"] == "TESTED"
    # Cycle N+1: what changed and why
    assert events[1]["cycle_id"] == "c2"
    assert events[1]["prior_lifecycle"] == "TESTED"
    assert events[1]["new_lifecycle"] == "INTEGRATED"
    assert events[1]["transition_reason"]  # a reason is always recorded
    assert events[1]["evidence_refs"]  # supporting evidence is preserved
    assert events[1]["temporal_classification"] == "CURRENT"


def test_contradictory_transition_recorded_with_reason(kernel: FederationKernel, store: FederationStore):
    now = datetime.now(timezone.utc)
    kernel.ingest_report(make_dat_ai_payload(cycle_id="c1", zoning_lifecycle="INTEGRATED", timestamp=now.isoformat()))
    later = (now + timedelta(minutes=1)).isoformat()
    kernel.ingest_report(
        make_dat_ai_payload(cycle_id="c2", zoning_lifecycle="IMPLEMENTED", timestamp=later, findings=["unrelated"])
    )
    events = store.get_state_events("dat_ai", "zoning_api")
    assert events[1]["executive_state_class"] == "CONTRADICTORY"
    assert "contradictory" in events[1]["transition_reason"].lower()


def test_duplicate_ingest_does_not_add_a_state_event(kernel: FederationKernel, store: FederationStore):
    payload = make_dat_ai_payload(cycle_id="dup")
    kernel.ingest_report(payload)
    count_before = store.count_state_events("dat_ai")
    kernel.ingest_report(payload)  # duplicate
    count_after = store.count_state_events("dat_ai")
    assert count_after == count_before  # materialized state and history both untouched


def test_current_materialized_state_coexists_with_immutable_history(kernel: FederationKernel, store: FederationStore):
    now = datetime.now(timezone.utc)
    kernel.ingest_report(make_dat_ai_payload(cycle_id="c1", zoning_lifecycle="TESTED", timestamp=now.isoformat()))
    later = (now + timedelta(minutes=1)).isoformat()
    result = kernel.ingest_report(
        make_dat_ai_payload(cycle_id="c2", zoning_lifecycle="INTEGRATED", timestamp=later, findings=["zoning_api: advanced"])
    )

    # Current materialized state shows only the latest.
    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["zoning_api"]["reported_lifecycle"] == "INTEGRATED"

    # But the full history is still queryable.
    events = store.get_state_events("dat_ai", "zoning_api")
    assert [e["new_lifecycle"] for e in events] == ["TESTED", "INTEGRATED"]
