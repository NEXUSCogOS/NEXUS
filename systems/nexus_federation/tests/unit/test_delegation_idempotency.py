"""Delegation idempotency tests.

Proves: first processing -> 1 delegation; duplicate report -> still 1;
restart + duplicate -> still 1; a new, materially different finding ->
a new delegation is allowed.
"""

from __future__ import annotations

from delegation.idempotency import compute_idempotency_key
from kernel import FederationKernel
from persistence.db import FederationStore
from relevance.router import RelevanceSignal
from tests.conftest import make_dat_ai_payload


def _signal(*, parent_mission_id="cycle-A", category="zoning_change", materiality=0.9):
    return RelevanceSignal(
        institution="dat_ai",
        capability_name="zoning_api",
        category=category,
        materiality=materiality,
        materiality_basis="test",
        evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
        parent_mission_id=parent_mission_id,
    )


def test_idempotency_key_is_deterministic_and_stable():
    k1 = compute_idempotency_key(institution="dat_ai", cycle_id="c1", capability_name="zoning_api", category="zoning_change")
    k2 = compute_idempotency_key(institution="dat_ai", cycle_id="c1", capability_name="zoning_api", category="zoning_change")
    assert k1 == k2


def test_idempotency_key_differs_for_different_cycle():
    k1 = compute_idempotency_key(institution="dat_ai", cycle_id="c1", capability_name="zoning_api", category="zoning_change")
    k2 = compute_idempotency_key(institution="dat_ai", cycle_id="c2", capability_name="zoning_api", category="zoning_change")
    assert k1 != k2


def test_first_processing_yields_one_delegation(kernel: FederationKernel):
    payload = make_dat_ai_payload(cycle_id="cycle-A")
    result = kernel.ingest_report(payload, relevance_signals=[_signal(parent_mission_id="cycle-A")])
    assert len(result.delegations) == 1
    assert kernel.store.count_delegations() == 1


def test_duplicate_report_still_one_delegation(kernel: FederationKernel):
    payload = make_dat_ai_payload(cycle_id="cycle-A")
    kernel.ingest_report(payload, relevance_signals=[_signal(parent_mission_id="cycle-A")])
    result2 = kernel.ingest_report(payload, relevance_signals=[_signal(parent_mission_id="cycle-A")])
    assert result2.temporal_classification == "DUPLICATE"
    assert kernel.store.count_delegations() == 1
    assert result2.delegations_suppressed_as_duplicate == 1


def test_restart_plus_duplicate_still_one_delegation(tmp_path):
    db_path = tmp_path / "idem.db"
    payload = make_dat_ai_payload(cycle_id="cycle-A")

    kernel1 = FederationKernel(FederationStore(db_path))
    kernel1.ingest_report(payload, relevance_signals=[_signal(parent_mission_id="cycle-A")])

    # "restart": brand-new kernel/store objects, same file
    kernel2 = FederationKernel(FederationStore(db_path))
    result = kernel2.ingest_report(payload, relevance_signals=[_signal(parent_mission_id="cycle-A")])

    assert result.temporal_classification == "DUPLICATE"
    assert kernel2.store.count_delegations() == 1


def test_new_materially_different_finding_allows_new_delegation(kernel: FederationKernel):
    payload_a = make_dat_ai_payload(cycle_id="cycle-A")
    kernel.ingest_report(payload_a, relevance_signals=[_signal(parent_mission_id="cycle-A")])

    later = None
    import datetime as _dt

    later = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(minutes=1)).isoformat()
    payload_b = make_dat_ai_payload(cycle_id="cycle-B", timestamp=later)
    kernel.ingest_report(payload_b, relevance_signals=[_signal(parent_mission_id="cycle-B")])

    assert kernel.store.count_delegations() == 2


def test_delegation_before_persistence_crash_recovers_to_exactly_one(tmp_path):
    """Simulates the 'before delegation persistence' crash point: the
    accepted cycle is committed (report_log + registry + state_events),
    but the process 'crashes' before relevance/delegation ever runs. A
    retry (now classified DUPLICATE, since the cycle is already accepted)
    must still be able to produce the one delegation that was never made
    -- and exactly one, not two, on a further retry after that."""
    db_path = tmp_path / "crash.db"
    payload = make_dat_ai_payload(cycle_id="cycle-A")

    # First call: ingest with NO relevance signals at all (simulates the
    # crash occurring before the caller ever attempts delegation).
    kernel1 = FederationKernel(FederationStore(db_path))
    result1 = kernel1.ingest_report(payload)
    assert kernel1.store.count_delegations() == 0

    # "Restart" + retry with the signal now supplied: the cycle is
    # DUPLICATE, but delegation must still be attempted and succeed once.
    kernel2 = FederationKernel(FederationStore(db_path))
    result2 = kernel2.ingest_report(payload, relevance_signals=[_signal(parent_mission_id="cycle-A")])
    assert result2.temporal_classification == "DUPLICATE"
    assert kernel2.store.count_delegations() == 1
    assert len(result2.delegations) == 1

    # A further retry must not create a second delegation.
    kernel3 = FederationKernel(FederationStore(db_path))
    result3 = kernel3.ingest_report(payload, relevance_signals=[_signal(parent_mission_id="cycle-A")])
    assert kernel3.store.count_delegations() == 1
    assert result3.delegations_suppressed_as_duplicate == 1
