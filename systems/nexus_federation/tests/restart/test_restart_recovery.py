"""RESTART/RECOVERY tests.

Proves: last accepted state survives a process restart, evidence links
survive, duplicates do not regenerate delegations, stale state becomes
stale correctly across a restart, and no fabricated replacement state
appears when a fresh process re-reads the same store.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kernel import FederationKernel
from persistence.db import FederationStore
from state.temporal import STALE_THRESHOLD, classify_age_only
from tests.conftest import make_dat_ai_payload


def test_last_accepted_state_survives_restart(tmp_path):
    db_path = tmp_path / "f1.db"
    kernel1 = FederationKernel(FederationStore(db_path))
    result1 = kernel1.ingest_report(make_dat_ai_payload(cycle_id="c1", zoning_lifecycle="INTEGRATED"))

    # "Restart": new process-equivalent objects, same underlying file.
    kernel2 = FederationKernel(FederationStore(db_path))
    entry_after_restart = kernel2.store.get_registry_entry("dat_ai")

    assert entry_after_restart is not None
    assert entry_after_restart == result1.registry_entry


def test_evidence_baselines_survive_restart(tmp_path):
    db_path = tmp_path / "f1.db"
    kernel1 = FederationKernel(FederationStore(db_path))
    kernel1.ingest_report(make_dat_ai_payload(cycle_id="c1"))

    kernel2 = FederationKernel(FederationStore(db_path))
    baseline = kernel2.store.get_evidence_baseline("dat_ai", "DATAI_CANONICAL_TEST_BASELINE.md")
    assert baseline is not None
    assert len(baseline) == 64  # a real sha256 hex digest, not a placeholder


def test_duplicate_after_restart_does_not_regenerate_delegation(tmp_path):
    db_path = tmp_path / "f1.db"
    payload = make_dat_ai_payload(cycle_id="stable-cycle")

    kernel1 = FederationKernel(FederationStore(db_path))
    kernel1.ingest_report(payload)
    delegations_before = kernel1.store.count_delegations()

    kernel2 = FederationKernel(FederationStore(db_path))
    result = kernel2.ingest_report(payload)  # same cycle_id -> DUPLICATE
    delegations_after = kernel2.store.count_delegations()

    assert result.temporal_classification == "DUPLICATE"
    assert delegations_after == delegations_before  # no new delegation from a duplicate


def test_stale_state_becomes_stale_correctly_across_restart(tmp_path):
    db_path = tmp_path / "f1.db"
    old_ts = (datetime.now(timezone.utc) - STALE_THRESHOLD - timedelta(hours=2)).isoformat()

    kernel1 = FederationKernel(FederationStore(db_path))
    kernel1.ingest_report(make_dat_ai_payload(cycle_id="c1", timestamp=old_ts))

    # After "restart", re-query the age-based classification (not the
    # ingest-time classification, which was computed once and stored) --
    # proves staleness is re-derivable from the persisted timestamp alone,
    # not dependent on in-memory state that a restart would have lost.
    kernel2 = FederationKernel(FederationStore(db_path))
    entry = kernel2.store.get_registry_entry("dat_ai")
    reclassified = classify_age_only(entry["last_report_timestamp"])
    assert reclassified.value in ("STALE", "EXPIRED")


def test_no_fabricated_replacement_state_after_restart_with_no_new_reports(tmp_path):
    """A restart with zero new reports must show EXACTLY the last accepted
    state -- not an empty/default/fabricated placeholder."""
    db_path = tmp_path / "f1.db"
    kernel1 = FederationKernel(FederationStore(db_path))
    result1 = kernel1.ingest_report(make_dat_ai_payload(cycle_id="c1"))

    kernel2 = FederationKernel(FederationStore(db_path))
    # Query without ingesting anything new.
    entry = kernel2.store.get_registry_entry("dat_ai")
    assert entry == result1.registry_entry
    all_entries = kernel2.store.all_registry_entries()
    assert len(all_entries) == 1  # exactly the one real institution, no phantom entries
