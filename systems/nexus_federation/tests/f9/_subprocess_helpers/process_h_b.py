#!/usr/bin/env python3
"""PHASE H PROCESS B: genuine subprocess memory-recovery helper.

Fresh interpreter, fresh ExecutiveCoordinator, same FederationStore file.
Recalls episode, reconstructs WHY/HOW, recalls semantic memory, verifies
policy reference. Prints os.getpid() and verification results.

Usage: process_h_b.py <db_path>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.environ["FEDERATION_ROOT"])
sys.path.insert(0, os.environ["DAT_AI_ROOT"])

from executive.coordinator import ExecutiveCoordinator  # noqa: E402
from persistence.db import FederationStore  # noqa: E402


def main() -> None:
    db_path = sys.argv[1]
    store = FederationStore(db_path)
    coordinator = ExecutiveCoordinator(store)

    checks = {}
    delegation_id = "mission_h_subprocess_test"

    # Recall episode
    episode = coordinator.recall_episode("episode_h_subprocess_1")
    checks["episode_recalled"] = episode is not None
    checks["episode_links_mission"] = episode is not None and delegation_id in episode["mission_ids"]
    checks["episode_links_policy"] = episode is not None and "pv_h_subprocess_1" in episode["policy_versions"]

    # WHY/HOW reconstruction, from persistence alone
    why_how = coordinator.reconstruct_why_how(delegation_id)
    checks["why_how_has_lifecycle"] = len(why_how["lifecycle_history"]) > 0
    checks["why_how_current_state_completed"] = why_how["current_state"] == "COMPLETED"
    checks["why_how_has_outcome"] = len(why_how["outcomes"]) > 0
    checks["why_how_outcome_success"] = (
        len(why_how["outcomes"]) > 0 and why_how["outcomes"][0]["outcome_class"] == "SUCCESS"
    )
    checks["why_how_has_related_episode"] = len(why_how["related_episodes"]) > 0

    # Recall semantic memory
    semantic = coordinator.recall_semantic_fact("sem_h_subprocess_1")
    checks["semantic_recalled"] = semantic is not None
    checks["semantic_status_active"] = semantic is not None and semantic["status"] == "ACTIVE"

    # Verify policy reference (procedural memory = Phase G registry)
    policy_context = coordinator.recall_policy_context("mission_lifecycle_policy_h")
    checks["policy_context_recalled"] = policy_context is not None
    checks["policy_context_active"] = policy_context is not None and policy_context["status"] == "ACTIVE"

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
