#!/usr/bin/env python3
"""PHASE H PROCESS A: genuine subprocess memory-recovery helper.

Creates a mission episode (with lifecycle + outcome + policy version
reference), and a semantic memory item. Prints os.getpid() and state.

Usage: process_h_a.py <db_path>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.environ["FEDERATION_ROOT"])
sys.path.insert(0, os.environ["DAT_AI_ROOT"])

from executive.coordinator import ExecutiveCoordinator  # noqa: E402
from executive.mission_state import MissionState  # noqa: E402
from executive.governance import PolicyVersion, PolicyType, PolicyVersionStatus  # noqa: E402
from executive.outcome import OutcomeEvaluation, OutcomeClass  # noqa: E402
from executive.memory import Episode, EpisodeType, SemanticMemoryItem  # noqa: E402
from persistence.db import FederationStore  # noqa: E402
from datetime import datetime, timezone  # noqa: E402


def main() -> None:
    db_path = sys.argv[1]
    store = FederationStore(db_path)
    coordinator = ExecutiveCoordinator(store)

    delegation_id = "mission_h_subprocess_test"

    # Policy version referenced by this mission
    pv = PolicyVersion(
        policy_version_id="pv_h_subprocess_1",
        policy_id="mission_lifecycle_policy_h",
        version=1,
        policy_type=PolicyType.MISSION_LIFECYCLE,
        configuration={"max_retries": 3},
    )
    coordinator.create_policy_version(pv)
    coordinator.activate_policy_version("pv_h_subprocess_1", "mission_lifecycle_policy_h")

    # Mission lifecycle
    coordinator.transition_mission(delegation_id, MissionState.PROPOSED, "H subprocess test start")
    coordinator.transition_mission(delegation_id, MissionState.VALIDATED, "validated")
    coordinator.transition_mission(delegation_id, MissionState.QUEUED, "queued")
    coordinator.transition_mission(delegation_id, MissionState.CLAIMED, "claimed")
    coordinator.transition_mission(delegation_id, MissionState.RUNNING, "running")
    coordinator.transition_mission(delegation_id, MissionState.COMPLETED, "completed successfully")

    # Outcome
    outcome = OutcomeEvaluation(
        outcome_id="outcome_h_subprocess_1",
        mission_id=delegation_id,
        delegation_id=delegation_id,
        outcome_class=OutcomeClass.SUCCESS,
        evaluated_at=datetime.now(timezone.utc),
        objective="verify Phase H subprocess memory recall",
        success_criteria=["criterion_1"],
        criteria_met=["criterion_1"],
        evidence_refs=["ev_h_subprocess_1"],
        policy_version="pv_h_subprocess_1",
    )
    coordinator.record_outcome(outcome)

    # Episode index linking everything
    episode = Episode(
        episode_id="episode_h_subprocess_1",
        episode_type=EpisodeType.MISSION_LIFECYCLE,
        root_trigger_id="trigger_h_subprocess_test",
        mission_ids=[delegation_id],
        institution_ids=["sentinel"],
        outcome_ids=["outcome_h_subprocess_1"],
        evidence_refs=["ev_h_subprocess_1"],
        policy_versions=["pv_h_subprocess_1"],
        status="CLOSED",
    )
    coordinator.create_episode(episode)

    # Semantic memory item (explicit promotion criteria: STRUCTURAL_INVARIANT)
    sem = SemanticMemoryItem(
        semantic_id="sem_h_subprocess_1",
        statement="Phase H mission lifecycle policy references are stable across subprocess restarts",
        claim_class="STRUCTURAL_INVARIANT",
        evidence_refs=["ev_h_subprocess_1"],
        confidence_basis="verified via genuine subprocess restart test",
    )
    semantic_id, created, _ = coordinator.record_semantic_memory(sem)

    store.checkpoint()

    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "delegation_id": delegation_id,
                "policy_activated": True,
                "outcome_recorded": True,
                "episode_created": True,
                "semantic_created": created,
                "semantic_id": semantic_id,
            }
        )
    )


if __name__ == "__main__":
    main()
