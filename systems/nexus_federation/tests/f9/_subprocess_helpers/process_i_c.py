#!/usr/bin/env python3
"""PHASE I PROCESS C: genuine subprocess loop test.

Fresh interpreter. Reconstructs the complete causal chain (event -> mission
-> lifecycle -> outcome -> memory) purely from FederationStore, verifies
exactly one semantic completion occurred (not two, despite two claim
attempts across Process A and Process B), and records a memory episode.

Usage: process_i_c.py <db_path> <event_id> <delegation_id>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.environ["FEDERATION_ROOT"])
sys.path.insert(0, os.environ["DAT_AI_ROOT"])

from executive.coordinator import ExecutiveCoordinator  # noqa: E402
from executive.memory import Episode, EpisodeType  # noqa: E402
from persistence.db import FederationStore  # noqa: E402


def main() -> None:
    db_path = sys.argv[1]
    event_id = sys.argv[2]
    delegation_id = sys.argv[3]

    store = FederationStore(db_path)
    coordinator = ExecutiveCoordinator(store)

    checks = {}

    # Reconstruct causal chain: event -> mission
    event = coordinator.get_event(event_id)
    checks["event_recoverable"] = event is not None
    checks["event_links_to_mission"] = event is not None and event["resulting_delegation_id"] == delegation_id

    # WHY/HOW reconstruction from persistence alone
    why_how = coordinator.reconstruct_why_how(delegation_id)
    checks["lifecycle_reconstructible"] = len(why_how["lifecycle_history"]) > 0
    checks["exactly_one_semantic_completion"] = (
        sum(1 for e in why_how["lifecycle_history"] if e["new_state"] == "COMPLETED") == 1
    )
    checks["final_state_completed"] = why_how["current_state"] == "COMPLETED"
    checks["outcome_present"] = len(why_how["outcomes"]) == 1
    checks["outcome_success"] = (
        len(why_how["outcomes"]) == 1 and why_how["outcomes"][0]["outcome_class"] == "SUCCESS"
    )

    # Verify BOTH claim attempts are visible in history (process_a's initial
    # claim + process_b's reclaim), proving no silent duplicate work --
    # exactly one CLAIMED->RUNNING->COMPLETED chain reached completion.
    claim_events = [e for e in why_how["lifecycle_history"] if e["new_state"] == "CLAIMED"]
    checks["both_claim_attempts_recorded"] = len(claim_events) == 2

    # Record memory episode for this recovered mission
    episode = Episode(
        episode_id=f"episode_{delegation_id}",
        episode_type=EpisodeType.MISSION_LIFECYCLE,
        root_trigger_id=event_id,
        mission_ids=[delegation_id],
        institution_ids=["sentinel"],
        outcome_ids=[why_how["outcomes"][0]["outcome_id"]] if why_how["outcomes"] else [],
        status="CLOSED",
    )
    episode_success, _ = coordinator.create_episode(episode)
    checks["episode_created"] = episode_success

    recalled_episode = coordinator.recall_episode(f"episode_{delegation_id}")
    checks["episode_recallable"] = recalled_episode is not None

    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "checks": checks,
                "all_passed": all(checks.values()),
            }
        )
    )


if __name__ == "__main__":
    main()
