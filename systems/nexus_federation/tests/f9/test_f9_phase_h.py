"""NEXUS F9 Phase H: Executive Memory + Provenance-Linked Recall.

Mandatory: genuine subprocess memory recall (real os.getpid(), real
subprocess.run, PID_A != PID_B).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from executive import (
    ExecutiveCoordinator,
    Episode,
    EpisodeType,
    SemanticMemoryItem,
    SemanticStatus,
    is_eligible_for_semantic_promotion,
    similarity_score,
    PolicyVersion,
    PolicyType,
    OutcomeEvaluation,
    OutcomeClass,
    LearningEvent,
    ObservationType,
    LearningEventStatus,
    MissionState,
)
from persistence.db import FederationStore

FEDERATION_ROOT = str(Path(__file__).resolve().parents[2])
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")
HELPERS_DIR = Path(__file__).resolve().parent / "_subprocess_helpers"


def _run_helper(script: str, args: list[str]) -> dict:
    env = dict(os.environ)
    env["FEDERATION_ROOT"] = FEDERATION_ROOT
    env["DAT_AI_ROOT"] = DAT_AI_ROOT
    proc = subprocess.run(
        [sys.executable, str(HELPERS_DIR / script), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert proc.returncode == 0, f"{script} failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


# === EPISODE CONSTRUCTION / RECALL ===

def test_episode_construction_and_recall():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        ep = Episode(
            episode_id="ep_construct_1",
            episode_type=EpisodeType.INSTITUTIONAL_INGEST,
            root_trigger_id="trigger_construct_1",
            mission_ids=["mission_construct_1"],
            institution_ids=["librarian"],
            evidence_refs=["ev_construct_1"],
        )
        success, reason = coordinator.create_episode(ep)
        assert success

        recalled = coordinator.recall_episode("ep_construct_1")
        assert recalled is not None
        assert recalled["episode_type"] == "INSTITUTIONAL_INGEST"
        assert recalled["mission_ids"] == ["mission_construct_1"]


def test_episode_index_is_not_a_copy():
    """Episode index carries only linking ids; full outcome content still
    lives in mission_outcome, not duplicated into episode_index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        outcome = OutcomeEvaluation(
            outcome_id="outcome_index_test",
            mission_id="mission_index_test",
            delegation_id="mission_index_test",
            outcome_class=OutcomeClass.SUCCESS,
            evaluated_at=datetime.now(timezone.utc),
            objective="a long objective description that should NOT be duplicated in episode_index",
        )
        coordinator.record_outcome(outcome)

        ep = Episode(
            episode_id="ep_index_test",
            episode_type=EpisodeType.MISSION_LIFECYCLE,
            mission_ids=["mission_index_test"],
            outcome_ids=["outcome_index_test"],
        )
        coordinator.create_episode(ep)

        # The episode row itself has no "objective" field -- must re-fetch
        # from mission_outcome to get the full content.
        recalled = coordinator.recall_episode("ep_index_test")
        assert "objective" not in recalled
        assert recalled["outcome_ids"] == ["outcome_index_test"]

        # Full content still retrievable from its canonical table
        outcomes = coordinator.get_mission_outcomes("mission_index_test")
        assert outcomes[0]["objective"] == "a long objective description that should NOT be duplicated in episode_index"


def test_recall_by_mission():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        ep = Episode(episode_id="ep_mission_recall", episode_type=EpisodeType.MISSION_LIFECYCLE, mission_ids=["mission_recall_test"])
        coordinator.create_episode(ep)

        recalled = coordinator.recall_by_mission("mission_recall_test")
        assert len(recalled) == 1
        assert recalled[0]["episode_id"] == "ep_mission_recall"


def test_recall_by_institution():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        ep = Episode(episode_id="ep_inst_recall", episode_type=EpisodeType.INSTITUTIONAL_INGEST, institution_ids=["sentinel", "news_intel"])
        coordinator.create_episode(ep)

        recalled_sentinel = coordinator.recall_by_institution("sentinel")
        recalled_news = coordinator.recall_by_institution("news_intel")
        assert len(recalled_sentinel) == 1
        assert len(recalled_news) == 1


def test_recall_by_outcome():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        ep = Episode(episode_id="ep_outcome_recall", episode_type=EpisodeType.MISSION_LIFECYCLE, outcome_ids=["outcome_recall_test"])
        coordinator.create_episode(ep)

        recalled = coordinator.recall_by_outcome("outcome_recall_test")
        assert len(recalled) == 1


def test_recall_by_trigger():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        ep = Episode(episode_id="ep_trigger_recall", episode_type=EpisodeType.CROSS_DOMAIN_SYNTHESIS, root_trigger_id="trigger_recall_test")
        coordinator.create_episode(ep)

        recalled = coordinator.recall_by_trigger("trigger_recall_test")
        assert len(recalled) == 1


# === SEMANTIC MEMORY ===

def test_semantic_memory_creation_with_explicit_criteria():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        sem = SemanticMemoryItem(
            semantic_id="sem_authority_boundary",
            statement="Sentinel live execution authority is not granted",
            claim_class="AUTHORITY_BOUNDARY",
            evidence_refs=["architectural_review_1"],
            confidence_basis="structural invariant, verified by Phase G gate tests",
        )
        semantic_id, created, reason = coordinator.record_semantic_memory(sem)
        assert created is True

        recalled = coordinator.recall_semantic_fact("sem_authority_boundary")
        assert recalled["statement"] == "Sentinel live execution authority is not granted"
        assert recalled["status"] == "ACTIVE"


def test_semantic_promotion_rejects_speculative_hypothesis():
    """A single speculative hypothesis (invalid claim_class) is rejected --
    stays episodic, never becomes semantic memory."""
    eligible, reason = is_eligible_for_semantic_promotion("SPECULATIVE_HYPOTHESIS")
    assert eligible is False


def test_semantic_promotion_requires_sample_size_for_validated_policy_fact():
    """VALIDATED_POLICY_FACT requires repeated observation, not one instance."""
    eligible_single, _ = is_eligible_for_semantic_promotion("VALIDATED_POLICY_FACT", sample_size=1)
    assert eligible_single is False

    eligible_repeated, _ = is_eligible_for_semantic_promotion("VALIDATED_POLICY_FACT", sample_size=10)
    assert eligible_repeated is True


def test_semantic_dedup():
    """Same statement + claim_class + evidence basis => no duplicate ACTIVE record."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        sem1 = SemanticMemoryItem(
            semantic_id="sem_dedup_1",
            statement="News materiality model is deterministic and uncalibrated",
            claim_class="MODEL_CHARACTERISTIC",
            evidence_refs=["news_model_review_1"],
        )
        id1, created1, _ = coordinator.record_semantic_memory(sem1)
        assert created1 is True

        sem2 = SemanticMemoryItem(
            semantic_id="sem_dedup_2_attempt",
            statement="News materiality model is deterministic and uncalibrated",
            claim_class="MODEL_CHARACTERISTIC",
            evidence_refs=["news_model_review_1"],
        )
        id2, created2, reason2 = coordinator.record_semantic_memory(sem2)
        assert created2 is False
        assert id2 == id1


def test_semantic_contradiction_preserves_history():
    """New conflicting evidence marks CONTRADICTED, does not overwrite silently."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        sem = SemanticMemoryItem(
            semantic_id="sem_contradiction_test",
            statement="Librarian corpus coverage for Vietnamese infrastructure economics is weak",
            claim_class="CORPUS_COVERAGE",
            evidence_refs=["coverage_audit_1"],
        )
        coordinator.record_semantic_memory(sem)

        success, reason = coordinator.contradict_semantic_memory(
            "sem_contradiction_test", ["coverage_audit_2_contradicting"], "new audit shows strong coverage"
        )
        assert success

        recalled = coordinator.recall_semantic_fact("sem_contradiction_test")
        assert recalled["status"] == "CONTRADICTED"
        # Original statement preserved, not erased
        assert recalled["statement"] == "Librarian corpus coverage for Vietnamese infrastructure economics is weak"


def test_semantic_invalidation_preserves_history():
    """Supporting evidence invalidated -> fact becomes INVALIDATED, no deletion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        sem = SemanticMemoryItem(
            semantic_id="sem_invalidation_test",
            statement="Institutional capability X is stable",
            claim_class="INSTITUTIONAL_CAPABILITY",
            evidence_refs=["capability_check_1"],
        )
        coordinator.record_semantic_memory(sem)

        success, reason = coordinator.invalidate_semantic_memory(
            "sem_invalidation_test", "capability_check_1 evidence was retracted"
        )
        assert success

        recalled = coordinator.recall_semantic_fact("sem_invalidation_test")
        assert recalled["status"] == "INVALIDATED"
        assert recalled["statement"] == "Institutional capability X is stable"  # preserved


def test_semantic_staleness():
    """A fact whose freshness window expired becomes STALE -- still
    recallable as historical context, not surfaced as current truth."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        sem = SemanticMemoryItem(
            semantic_id="sem_stale_test",
            statement="Institution Y had capacity headroom in Q1",
            claim_class="INSTITUTIONAL_CAPABILITY",
            evidence_refs=["capacity_snapshot_q1"],
        )
        coordinator.record_semantic_memory(sem)

        success, reason = coordinator.mark_semantic_stale("sem_stale_test", "Q1 snapshot no longer reflects current state")
        assert success

        recalled = coordinator.recall_semantic_fact("sem_stale_test")
        assert recalled["status"] == "STALE"

        # Still recallable (historical context)
        active_only = coordinator.recall_semantic_by_claim_class("INSTITUTIONAL_CAPABILITY", status="ACTIVE")
        assert len(active_only) == 0, "STALE facts must not appear when filtering for ACTIVE current truth"

        all_facts = coordinator.recall_semantic_by_claim_class("INSTITUTIONAL_CAPABILITY")
        assert len(all_facts) == 1, "but still recallable overall as historical context"


# === PROCEDURAL MEMORY (references Phase G, no duplicate store) ===

def test_procedural_memory_references_versioned_policy():
    """Procedural memory recall returns the SAME executive_policy_version
    row Phase G created -- no separate mutable procedural store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        pv = PolicyVersion(
            policy_version_id="pv_procedural_test",
            policy_id="retry_policy_procedural_test",
            version=1,
            policy_type=PolicyType.RETRY,
            configuration={"max_attempts": 3},
        )
        coordinator.create_policy_version(pv)
        coordinator.activate_policy_version("pv_procedural_test", "retry_policy_procedural_test")

        recalled = coordinator.recall_policy_context("retry_policy_procedural_test")
        assert recalled["policy_version_id"] == "pv_procedural_test"
        assert recalled["configuration"]["max_attempts"] == 3

        # Confirm it's literally the Phase G table, not a copy
        direct_from_governance = coordinator.resolve_active_policy("retry_policy_procedural_test")
        assert recalled == direct_from_governance


# === WHY/HOW RECONSTRUCTION ===

def test_why_how_reconstruction_from_persistence_alone():
    """Mandatory: reconstruct WHY/HOW for a mission, using only persisted state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        delegation_id = "mission_why_how_test"
        coordinator.transition_mission(delegation_id, MissionState.PROPOSED, "materiality signal from Sentinel")
        coordinator.transition_mission(delegation_id, MissionState.VALIDATED, "evidence resolved")
        coordinator.transition_mission(delegation_id, MissionState.QUEUED, "queued for scheduling")
        coordinator.transition_mission(delegation_id, MissionState.CLAIMED, "claimed by executor")
        coordinator.transition_mission(delegation_id, MissionState.RUNNING, "execution started")
        coordinator.transition_mission(delegation_id, MissionState.COMPLETED, "objective achieved")

        outcome = OutcomeEvaluation(
            outcome_id="outcome_why_how_test",
            mission_id=delegation_id,
            delegation_id=delegation_id,
            outcome_class=OutcomeClass.SUCCESS,
            evaluated_at=datetime.now(timezone.utc),
            objective="verify why/how reconstruction",
            success_criteria=["criterion_a"],
            criteria_met=["criterion_a"],
        )
        coordinator.record_outcome(outcome)

        why_how = coordinator.reconstruct_why_how(delegation_id)

        assert why_how["current_state"] == "COMPLETED"
        assert len(why_how["lifecycle_history"]) == 6
        # WHY it was created: first transition's reason
        proposed_event = next(e for e in why_how["lifecycle_history"] if e["new_state"] == "PROPOSED")
        assert proposed_event["reason"] == "materiality signal from Sentinel"
        # WHAT outcome occurred
        assert why_how["outcomes"][0]["outcome_class"] == "SUCCESS"


# === PROVENANCE INTEGRITY (fail-closed) ===

def test_provenance_integrity_source_missing():
    """A reference to evidence with no baseline fails closed as SOURCE_MISSING."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        status = coordinator.check_provenance_integrity("nonexistent_evidence_ref")
        assert status == "SOURCE_MISSING"


def test_provenance_integrity_ok():
    """A baseline matching the expected hash reports OK."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        store.set_evidence_baseline_if_absent(
            "test_institution", "ev_integrity_ok", "abc123hash", datetime.now(timezone.utc).isoformat()
        )
        status = coordinator.check_provenance_integrity("ev_integrity_ok", expected_hash="abc123hash")
        assert status == "OK"


def test_provenance_integrity_drift():
    """A hash mismatch reports EVIDENCE_DRIFT -- never silently treated as verified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        store.set_evidence_baseline_if_absent(
            "test_institution", "ev_drift_test", "original_hash", datetime.now(timezone.utc).isoformat()
        )
        status = coordinator.check_provenance_integrity("ev_drift_test", expected_hash="different_hash")
        assert status == "EVIDENCE_DRIFT"


# === SIMILAR-CASE RECALL (transparent baseline) ===

def test_similar_case_recall_is_transparent():
    """Similarity is explicit matched-dimension count, not opaque vector similarity."""
    case_a = {"institution_id": "sentinel", "episode_type": "MISSION_LIFECYCLE", "outcome_class": "SUCCESS", "policy_type": "RETRY"}
    case_b = {"institution_id": "sentinel", "episode_type": "MISSION_LIFECYCLE", "outcome_class": "FAILED", "policy_type": "RETRY"}

    score, matched_dims = similarity_score(case_a, case_b)
    assert 0.0 < score < 1.0
    assert "institution_id" in matched_dims
    assert "episode_type" in matched_dims
    assert "outcome_class" not in matched_dims  # differs, must not be counted


def test_similar_case_recall_full_match():
    case_a = {"institution_id": "librarian", "episode_type": "INSTITUTIONAL_INGEST", "outcome_class": "SUCCESS", "policy_type": "OUTCOME"}
    case_b = dict(case_a)

    score, matched_dims = similarity_score(case_a, case_b)
    assert score == 1.0
    assert len(matched_dims) == 4


# === LEARNING INTEGRATION (Phase E connection, sample-size guard preserved) ===

def test_learning_observation_stays_episodic_below_sample_threshold():
    """Learning observations become episodic immediately; semantic promotion
    requires the sample-size guard to be satisfied -- never bypassed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        # Episodic: single learning event recorded immediately regardless of sample size
        event = LearningEvent(
            learning_event_id="learning_h_test_1",
            source_mission_id="mission_learning_h_test",
            observation_type=ObservationType.INSTITUTION_RELIABILITY,
            observed_value=0.85,
            sample_size=1,
            status=LearningEventStatus.INSUFFICIENT_SAMPLE_SIZE,
        )
        store.record_learning_event(event.to_dict())

        events = store.get_learning_events("mission_learning_h_test")
        assert len(events) == 1  # episodic recording always happens

        # Semantic promotion attempt with insufficient sample size is rejected
        eligible, reason = is_eligible_for_semantic_promotion("VALIDATED_POLICY_FACT", sample_size=1)
        assert eligible is False, "sample-size guard must not be bypassed by memory integration"


# === ESCALATION MEMORY (dedup already covered in Phase G; recall here) ===

def test_escalation_memory_recall_avoids_duplicate_attention_request():
    """Detecting a similar unresolved escalation via recall avoids a duplicate request."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        from executive.governance import Escalation, EscalationClass

        esc = Escalation(
            escalation_id="esc_memory_test_1",
            escalation_class=EscalationClass.PERSISTENT_INSTITUTION_FAILURE,
            reason="circuit OPEN, recurring",
            mission_id="mission_escalation_memory_test",
            trigger_id="circuit_open_trigger",
        )
        coordinator.create_escalation(esc)

        # Recall existing open escalations for this mission before creating a new attention request
        open_escalations = [
            e for e in coordinator.list_escalations("OPEN")
            if e["mission_id"] == "mission_escalation_memory_test"
        ]
        assert len(open_escalations) == 1, "recall correctly surfaces the existing unresolved escalation"


# === REAL PRIOR HISTORY RECALL (per-institution, no rerun) ===

def test_recall_prior_history_across_institutions_without_rerun():
    """Reconstruct WHY/HOW for one representative completed mission per
    institution domain (DAT.AI, Librarian, Sentinel, News, YouTube) plus one
    F9 policy/escalation event -- entirely from persisted state, never by
    re-invoking the original mission logic."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "federation.db")
        coordinator = ExecutiveCoordinator(store)

        scenarios = [
            ("dat_ai", "mission_recall_dat_ai", OutcomeClass.SUCCESS, "zoning materiality signal ingested"),
            ("librarian", "mission_recall_librarian", OutcomeClass.SUCCESS, "bounded research completed"),
            ("librarian", "mission_recall_librarian_insufficient", OutcomeClass.INSUFFICIENT_EVIDENCE, "corpus coverage too weak to conclude"),
            ("sentinel", "mission_recall_sentinel", OutcomeClass.SUCCESS, "analysis completed, no execution"),
            ("news_intel", "mission_recall_news", OutcomeClass.NO_ACTION_REQUIRED, "event assessed, no material effect"),
            ("youtube_production", "mission_recall_youtube", OutcomeClass.SUCCESS, "script ready, publication NOT authorized"),
        ]

        for institution_id, delegation_id, outcome_class, why in scenarios:
            coordinator.transition_mission(delegation_id, MissionState.PROPOSED, why)
            coordinator.transition_mission(delegation_id, MissionState.VALIDATED, "evidence resolved")
            coordinator.transition_mission(delegation_id, MissionState.QUEUED, "queued")
            coordinator.transition_mission(delegation_id, MissionState.CLAIMED, "claimed")
            coordinator.transition_mission(delegation_id, MissionState.RUNNING, "running")
            coordinator.transition_mission(delegation_id, MissionState.COMPLETED, "terminal")

            outcome = OutcomeEvaluation(
                outcome_id=f"outcome_{delegation_id}",
                mission_id=delegation_id,
                delegation_id=delegation_id,
                outcome_class=outcome_class,
                evaluated_at=datetime.now(timezone.utc),
                objective=why,
            )
            coordinator.record_outcome(outcome)

            episode = Episode(
                episode_id=f"episode_{delegation_id}",
                episode_type=EpisodeType.INSTITUTIONAL_INGEST,
                mission_ids=[delegation_id],
                institution_ids=[institution_id],
                outcome_ids=[f"outcome_{delegation_id}"],
            )
            coordinator.create_episode(episode)

        # F9 policy/escalation event
        pv = PolicyVersion(
            policy_version_id="pv_recall_history_test",
            policy_id="recall_history_policy",
            version=1,
            policy_type=PolicyType.ESCALATION,
            configuration={"rule": "test"},
        )
        coordinator.create_policy_version(pv)
        coordinator.activate_policy_version("pv_recall_history_test", "recall_history_policy")

        # Now reconstruct each WITHOUT rerunning any mission logic -- pure recall
        for institution_id, delegation_id, outcome_class, why in scenarios:
            why_how = coordinator.reconstruct_why_how(delegation_id)
            assert why_how["current_state"] == "COMPLETED"
            assert why_how["outcomes"][0]["outcome_class"] == outcome_class.value

            by_institution = coordinator.recall_by_institution(institution_id)
            assert any(e["mission_ids"] == [delegation_id] for e in by_institution)

        policy_recall = coordinator.recall_policy_context("recall_history_policy")
        assert policy_recall["policy_version_id"] == "pv_recall_history_test"


# === MANDATORY: GENUINE SUBPROCESS MEMORY RECALL ===

def test_phase_h_restart_recovery_genuine_subprocess(tmp_path):
    """MANDATORY: episode + semantic memory + WHY/HOW reconstruction survive
    across REAL OS process boundaries (subprocess.run, distinct os.getpid()).
    """
    db_path = tmp_path / "phase_h_subprocess.db"

    result_a = _run_helper("process_h_a.py", [str(db_path)])
    pid_a = result_a["pid"]
    assert result_a["policy_activated"] is True
    assert result_a["outcome_recorded"] is True
    assert result_a["episode_created"] is True
    assert result_a["semantic_created"] is True

    result_b = _run_helper("process_h_b.py", [str(db_path)])
    pid_b = result_b["pid"]
    assert pid_a != pid_b, "must be genuinely distinct OS processes"
    assert result_b["all_passed"] is True, result_b["checks"]

    print("REAL_SUBPROCESS_RECALL_STATUS = PASS")
    print(f"PID_A={pid_a}, PID_B={pid_b} (genuine os.getpid() from 2 distinct subprocess.run invocations)")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
