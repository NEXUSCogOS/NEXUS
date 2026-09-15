"""FAILURE tests: the 15 explicitly-numbered scenarios from the F3 mission
(section 21). Each proves safe degradation and/or idempotency -- never a
silent fabrication.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from contracts.generic import CapabilityLifecycle
from corpus import DatabaseConnectionPool, JsonContentStore
from delegation.schema import DelegationProposal
from kernel import FederationKernel
from persistence.db import FederationStore
from relevance.router import RelevanceSignal
from reporting.reporter import build_current_report
from runtime.delegation_inbox import poll_and_execute
from runtime.research_executor import INSUFFICIENT_EVIDENCE, execute_research_mission
from tests.integration.test_delegation_inbox import _make_proposal


# --------------------------------------------------------------------------- #
# 1. Librarian unavailable                                                    #
# --------------------------------------------------------------------------- #
def test_01_librarian_unavailable_delegation_stays_pending_safely(tmp_path):
    """No process ever polls for the delegation ('Librarian is down').
    NEXUS's own state must stay entirely consistent -- the delegation
    simply sits pending, durably, until Librarian polls later."""
    store = FederationStore(tmp_path / "f.db")
    store.append_delegation(_make_proposal())
    assert store.count_delivered("librarian") == 0
    assert store.count_delegations() == 1  # nothing lost, nothing corrupted


# --------------------------------------------------------------------------- #
# 2. Corpus unavailable                                                       #
# --------------------------------------------------------------------------- #
def test_02_corpus_unavailable_returns_insufficient_evidence_not_crash(tmp_path):
    """An empty/never-ingested data_dir (simulating corpus unavailability)
    must produce an honest INSUFFICIENT_EVIDENCE, not a crash and not a
    fabricated finding."""
    report = execute_research_mission(
        mission_id="m", objective="test", query="anything at all",
        data_dir=tmp_path / "nonexistent_data",
    )
    assert INSUFFICIENT_EVIDENCE in report.findings[0]


# --------------------------------------------------------------------------- #
# 3. External storage (content JSON) unavailable                             #
# --------------------------------------------------------------------------- #
def test_03_missing_content_shard_degrades_gracefully(tmp_path, real_data_dir):
    """A source's content JSON shard is simply absent (external storage
    unreachable for that shard) -- search must skip it, not crash."""
    import shutil

    isolated = tmp_path / "data"
    shutil.copytree(real_data_dir, isolated)
    content_dir = isolated / "content"
    for f in content_dir.glob("*.json"):
        f.unlink()  # remove all shards -- simulates total external storage unavailability

    report = execute_research_mission(
        mission_id="m", objective="test", query="ingestion provenance dedup", data_dir=isolated
    )
    assert INSUFFICIENT_EVIDENCE in report.findings[0]  # degrades honestly, does not crash


# --------------------------------------------------------------------------- #
# 4. Malformed delegation                                                    #
# --------------------------------------------------------------------------- #
def test_04_malformed_delegation_fails_loudly_not_silently(tmp_path, real_data_dir):
    """A delegation row missing a required field fails loudly (KeyError)
    rather than silently producing a fabricated report."""
    store = FederationStore(tmp_path / "f.db")
    malformed = _make_proposal()
    del malformed["objective"]
    store.append_delegation(malformed)

    with pytest.raises(KeyError):
        poll_and_execute(store, data_dir=real_data_dir)


# --------------------------------------------------------------------------- #
# 5. Duplicate delegation                                                    #
# --------------------------------------------------------------------------- #
def test_05_duplicate_delegation_claimed_once_only(tmp_path, real_data_dir):
    store = FederationStore(tmp_path / "f.db")
    store.append_delegation(_make_proposal())
    first = poll_and_execute(store, data_dir=real_data_dir)
    second = poll_and_execute(store, data_dir=real_data_dir)
    assert len(first) == 1
    assert len(second) == 0


# --------------------------------------------------------------------------- #
# 6. Stale delegation (delivered but not executed for a long time)           #
# --------------------------------------------------------------------------- #
def test_06_stale_undelivered_delegation_still_executes_correctly_when_finally_polled(tmp_path, real_data_dir):
    """A delegation nobody polled for a long time (but with NO ttl_deadline
    set) is still correctly executed once polling finally happens --
    'stale' alone (no expiry stated) is not the same as 'expired'."""
    store = FederationStore(tmp_path / "f.db")
    proposal = _make_proposal()
    assert proposal["ttl_deadline"] is None
    store.append_delegation(proposal)

    long_after = datetime.now(timezone.utc) + timedelta(days=30)
    executed = poll_and_execute(store, data_dir=real_data_dir, now=long_after)
    assert len(executed) == 1


# --------------------------------------------------------------------------- #
# 7. Unsupported authority request                                           #
# --------------------------------------------------------------------------- #
def test_07_unsupported_authority_request_structurally_rejected():
    """A delegation requesting authority above the phase ceiling (ANALYSE)
    cannot even be constructed -- structural, not conventional, rejection."""
    proposal = _make_proposal()
    proposal_kwargs = {k: v for k, v in proposal.items() if k != "authority"}
    with pytest.raises(ValidationError):
        DelegationProposal(**proposal_kwargs, authority="HIGH_CONSEQUENCE_ACTION")


# --------------------------------------------------------------------------- #
# 8. Insufficient evidence                                                   #
# --------------------------------------------------------------------------- #
def test_08_insufficient_evidence_is_a_valid_successful_outcome(real_data_dir):
    report = execute_research_mission(
        mission_id="m", objective="test",
        query="quantum chromodynamics lattice gauge theory", data_dir=real_data_dir,
    )
    assert report.operating_state.value != "UNAVAILABLE"  # a valid, successful report
    assert INSUFFICIENT_EVIDENCE in report.findings[0]


# --------------------------------------------------------------------------- #
# 9. Invalid citation/provenance (evidence_ref that no longer resolves)      #
# --------------------------------------------------------------------------- #
def test_09_stale_source_uri_resolves_as_missing_not_fabricated_as_verified():
    """Real corpus evidence_refs point at ~/Librarian paths that no longer
    exist on this machine (see LIBRARIAN_DONOR_FORENSIC_REPORT.md). NEXUS's
    own evidence resolver must report this honestly as unresolved."""
    from evidence.resolver import resolve_evidence_ref

    stale_ref = "${HOME}/Librarian/USER_MANUAL.md"
    resolution = resolve_evidence_ref(stale_ref)
    assert resolution.resolved is False  # honest MISSING, never fabricated as VERIFIED


# --------------------------------------------------------------------------- #
# 10. Corrupted evidence (unparseable content shard)                         #
# --------------------------------------------------------------------------- #
def test_10_corrupted_content_shard_degrades_safely(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "src_corrupted.json").write_text("{not valid json!!!", encoding="utf-8")

    store = JsonContentStore(content_dir)
    result = store.get_all("src_corrupted")  # must not raise
    assert result == {}


# --------------------------------------------------------------------------- #
# 11. Restart before execution                                               #
# --------------------------------------------------------------------------- #
def test_11_restart_before_execution_delegation_survives_and_executes(tmp_path, real_data_dir):
    db_path = tmp_path / "f.db"
    store1 = FederationStore(db_path)
    store1.append_delegation(_make_proposal())
    # "restart" happens before anyone ever polls
    store2 = FederationStore(db_path)
    executed = poll_and_execute(store2, data_dir=real_data_dir)
    assert len(executed) == 1


# --------------------------------------------------------------------------- #
# 12. Restart after execution, before NEXUS ingests the report               #
# --------------------------------------------------------------------------- #
def test_12_restart_after_execution_before_ingest_report_still_ingests_correctly(tmp_path, real_data_dir):
    db_path = tmp_path / "f.db"
    store1 = FederationStore(db_path)
    store1.append_delegation(_make_proposal())
    executed = poll_and_execute(store1, data_dir=real_data_dir)
    report = executed[0].report  # NEXUS has not ingested this yet -- simulate a crash here

    # "restart": brand-new kernel/store, same file
    store2 = FederationStore(db_path)
    kernel2 = FederationKernel(store2)
    result = kernel2.ingest_report(report)
    assert result.accepted is True
    assert store2.get_registry_entry("librarian") is not None


# --------------------------------------------------------------------------- #
# 13. Duplicate report                                                        #
# --------------------------------------------------------------------------- #
def test_13_duplicate_librarian_report_is_idempotent(tmp_path):
    store = FederationStore(tmp_path / "f.db")
    kernel = FederationKernel(store)
    report = build_current_report(mission_id="m", cycle_id="c1").model_dump(mode="json")

    r1 = kernel.ingest_report(report)
    r2 = kernel.ingest_report(report)
    assert r1.accepted is True
    assert r2.temporal_classification == "DUPLICATE"


# --------------------------------------------------------------------------- #
# 14. Contradictory research result                                          #
# --------------------------------------------------------------------------- #
def test_14_contradictory_librarian_capability_regression_flagged(tmp_path):
    store = FederationStore(tmp_path / "f.db")
    kernel = FederationKernel(store)

    now = datetime.now(timezone.utc)
    r1 = build_current_report(mission_id="m", cycle_id="c1")
    r1 = r1.model_copy(update={"timestamp": now.isoformat()})
    kernel.ingest_report(r1.model_dump(mode="json"))

    # Second cycle: corpus_retrieval regresses from TESTED to IMPLEMENTED
    # with no finding/limitation explaining why -> CONTRADICTORY.
    r2 = build_current_report(mission_id="m", cycle_id="c2", findings=["unrelated change"])
    caps = [c.model_copy() for c in r2.capability_statuses]
    for c in caps:
        if c.name == "corpus_retrieval":
            c.lifecycle = CapabilityLifecycle.IMPLEMENTED
    r2 = r2.model_copy(update={
        "timestamp": (now + timedelta(minutes=1)).isoformat(),
        "capability_statuses": caps,
    })
    result = kernel.ingest_report(r2.model_dump(mode="json"))
    states = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert states["corpus_retrieval"]["executive_state_class"] == "CONTRADICTORY"


# --------------------------------------------------------------------------- #
# 15. Expired mission TTL                                                     #
# --------------------------------------------------------------------------- #
def test_15_expired_ttl_not_executed_but_claimed(tmp_path, real_data_dir):
    store = FederationStore(tmp_path / "f.db")
    proposal = _make_proposal()
    proposal["ttl_deadline"] = "2020-01-01T00:00:00+00:00"  # long past
    store.append_delegation(proposal)

    executed = poll_and_execute(store, data_dir=real_data_dir)
    assert executed == []  # not executed
    record = store.get_delivery_record(proposal["proposal_id"])
    assert record["executed_at"] is not None  # but claimed, so it is never retried forever
    assert record["result_cycle_id"] == "EXPIRED_TTL_NOT_EXECUTED"
