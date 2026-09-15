"""Crash-point recovery tests (F2 mission section 3).

Each test simulates a process crash at one of the five named transaction
points by monkeypatching the exact call that would not have completed,
letting the resulting exception propagate (exactly as a real crash would
interrupt execution at that point), then verifying:
  - no partial canonical state was left behind, and
  - a clean retry recovers correctly, without duplicating or losing
    anything.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kernel import FederationKernel
from persistence.db import FederationStore
from relevance.router import RelevanceSignal
from tests.conftest import make_dat_ai_payload


def _signal(parent_mission_id="cycle-A"):
    return RelevanceSignal(
        institution="dat_ai",
        capability_name="zoning_api",
        category="zoning_change",
        materiality=0.9,
        materiality_basis="test",
        evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
        parent_mission_id=parent_mission_id,
    )


def test_crash_point_1_after_receipt_before_acceptance(tmp_path, monkeypatch):
    """Crash after schema validation (the report has been 'received' and
    is schema-valid) but before the accept/reject decision is even made --
    i.e. while reading prior state to classify this report temporally.
    No persistence call has been reached yet at this point in the real
    ingest_report flow, so nothing is written; a clean retry behaves
    exactly like a first-ever ingest."""
    db_path = tmp_path / "cp1.db"
    store = FederationStore(db_path)
    kernel = FederationKernel(store)
    payload = make_dat_ai_payload(cycle_id="c1")

    def _boom(*a, **kw):
        raise RuntimeError("simulated crash: process died before the accept/reject decision")

    monkeypatch.setattr(store, "last_accepted_report", _boom)
    with pytest.raises(RuntimeError):
        kernel.ingest_report(payload)

    assert store.count_reports() == 0
    assert store.all_registry_entries() == []

    monkeypatch.undo()
    result = kernel.ingest_report(payload)
    assert result.accepted is True
    assert store.count_reports() == 1


def test_crash_point_2_after_evidence_resolution_before_state_persistence(tmp_path, monkeypatch):
    """Crash after evidence resolution ran (ledger rows, baselines, and
    provenance records for the attempt are legitimately written -- these
    are additive audit rows, not canonical state) but before the atomic
    report_log+registry+state_events commit. No orphaned/partial canonical
    state must result, and a retry must be classified CURRENT (not
    DUPLICATE, since nothing was actually committed), fully reprocessing."""
    db_path = tmp_path / "cp2.db"
    store = FederationStore(db_path)
    kernel = FederationKernel(store)
    payload = make_dat_ai_payload(cycle_id="c1")

    def _boom(*a, **kw):
        raise RuntimeError("simulated crash: process died before commit_accepted_cycle")

    monkeypatch.setattr(store, "commit_accepted_cycle", _boom)
    with pytest.raises(RuntimeError):
        kernel.ingest_report(payload)

    # Evidence-resolution audit rows exist (the attempt genuinely happened)...
    assert store.count_evidence_resolutions() >= 1
    # ...but NO canonical state was committed.
    assert store.count_reports(accepted=1) == 0
    assert store.all_registry_entries() == []
    assert store.count_state_events("dat_ai") == 0

    monkeypatch.undo()
    result = kernel.ingest_report(payload)
    assert result.accepted is True
    assert result.temporal_classification == "CURRENT"  # NOT duplicate -- nothing was committed before
    assert len(store.all_registry_entries()) == 1
    assert store.count_state_events("dat_ai") >= 1


def test_crash_point_3_after_state_persistence_before_delegation(tmp_path, monkeypatch):
    """Crash after the atomic commit succeeded (report_log + registry +
    state_events all durable) but before relevance/delegation runs. The
    accepted cycle must not be lost or reprocessed from scratch (a retry
    is correctly DUPLICATE), and the missing delegation must still be
    produced -- exactly once -- when relevance signals are supplied on
    retry."""
    db_path = tmp_path / "cp3.db"
    store = FederationStore(db_path)
    kernel = FederationKernel(store)
    payload = make_dat_ai_payload(cycle_id="c1")

    def _boom(*a, **kw):
        raise RuntimeError("simulated crash: process died before relevance/delegation")

    monkeypatch.setattr(kernel, "_process_relevance", _boom)
    with pytest.raises(RuntimeError):
        kernel.ingest_report(payload, relevance_signals=[_signal("c1")])

    # State WAS committed -- this crash point is after that commit.
    assert len(store.all_registry_entries()) == 1
    assert store.count_reports(accepted=1) == 1
    assert store.count_delegations() == 0  # delegation never got to run

    monkeypatch.undo()
    result = kernel.ingest_report(payload, relevance_signals=[_signal("c1")])
    assert result.temporal_classification == "DUPLICATE"  # correctly recognized as already-accepted
    assert store.count_delegations() == 1  # the missing delegation is now produced, exactly once
    assert len(store.all_registry_entries()) == 1  # registry was never touched a second time


def test_crash_point_4_before_delegation_persistence_no_duplicate_on_retry(tmp_path):
    """'Before delegation persistence': assess_relevance() runs and
    produces a proposal, but the process dies before store.append_delegation
    durably records it. On retry, exactly one delegation exists -- not
    zero forever, not two."""
    db_path = tmp_path / "cp4.db"
    payload = make_dat_ai_payload(cycle_id="c1")

    kernel1 = FederationKernel(FederationStore(db_path))
    kernel1.ingest_report(payload)  # accept the cycle with NO delegation attempt (simulates the crash)
    assert kernel1.store.count_delegations() == 0

    kernel2 = FederationKernel(FederationStore(db_path))
    result = kernel2.ingest_report(payload, relevance_signals=[_signal("c1")])
    assert result.temporal_classification == "DUPLICATE"
    assert kernel2.store.count_delegations() == 1

    kernel3 = FederationKernel(FederationStore(db_path))
    result3 = kernel3.ingest_report(payload, relevance_signals=[_signal("c1")])
    assert kernel3.store.count_delegations() == 1  # not duplicated by the second retry
    assert result3.delegations_suppressed_as_duplicate == 1


def test_crash_point_5_after_delegation_persistence_fully_recovered_state(tmp_path):
    """'After delegation persistence': the whole cycle completed. A retry
    (duplicate) must show exactly the same, unfabricated final state --
    no phantom second delegation, no altered registry entry."""
    db_path = tmp_path / "cp5.db"
    payload = make_dat_ai_payload(cycle_id="c1")

    kernel1 = FederationKernel(FederationStore(db_path))
    result1 = kernel1.ingest_report(payload, relevance_signals=[_signal("c1")])
    assert len(result1.delegations) == 1

    kernel2 = FederationKernel(FederationStore(db_path))
    result2 = kernel2.ingest_report(payload, relevance_signals=[_signal("c1")])
    assert result2.temporal_classification == "DUPLICATE"
    assert kernel2.store.count_delegations() == 1
    assert result2.registry_entry == result1.registry_entry
