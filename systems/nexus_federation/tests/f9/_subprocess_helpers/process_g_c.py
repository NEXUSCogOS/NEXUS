#!/usr/bin/env python3
"""PHASE G PROCESS C: genuine subprocess restart-recovery helper.

Fresh interpreter, fresh FederationStore. Verifies escalation resolution
persisted, policy state is correct, and no duplicate escalation was
created for the same dedup condition. Prints os.getpid() and results.

Usage: process_g_c.py <db_path>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.environ["FEDERATION_ROOT"])
sys.path.insert(0, os.environ["DAT_AI_ROOT"])

from executive.coordinator import ExecutiveCoordinator  # noqa: E402
from executive.governance import Escalation, EscalationClass, EscalationSeverity  # noqa: E402
from persistence.db import FederationStore  # noqa: E402


def main() -> None:
    db_path = sys.argv[1]
    store = FederationStore(db_path)
    coordinator = ExecutiveCoordinator(store)

    checks = {}

    # Verify resolution persisted
    escalation = coordinator.get_escalation("esc_g_subprocess_1")
    checks["resolution_persisted"] = escalation is not None and escalation["status"] == "RESOLVED"
    checks["resolver_recorded"] = escalation is not None and escalation["resolver"] == "process_g_b"

    # Verify policy state correct
    active = coordinator.resolve_active_policy("resource_policy_subprocess_test")
    checks["v1_still_active"] = active is not None and active["version"] == 1

    # Attempt to create a semantically identical escalation -- since the
    # original is now RESOLVED (not OPEN/ACKNOWLEDGED), a new one for the
    # SAME dedup condition IS allowed (a materially new request after
    # resolution is legitimate, per the spec's "after escalation resolved,
    # materially new request may create a new one").
    esc_new = Escalation(
        escalation_id="esc_g_subprocess_2_after_resolution",
        escalation_class=EscalationClass.RESOURCE_BUDGET_EXCEEDED,
        reason="mission requested 150 cpu-seconds, ceiling is 100",
        severity=EscalationSeverity.MEDIUM,
        mission_id="mission_g_subprocess_test",
        trigger_id="trigger_g_subprocess_test",
    )
    created_after_resolution, _, _ = coordinator.create_escalation(esc_new)
    checks["new_escalation_allowed_after_resolution"] = created_after_resolution is True

    # But creating a THIRD one while the second is still OPEN must dedup
    esc_dup = Escalation(
        escalation_id="esc_g_subprocess_3_duplicate_attempt",
        escalation_class=EscalationClass.RESOURCE_BUDGET_EXCEEDED,
        reason="mission requested 150 cpu-seconds, ceiling is 100",
        severity=EscalationSeverity.MEDIUM,
        mission_id="mission_g_subprocess_test",
        trigger_id="trigger_g_subprocess_test",
    )
    created_dup, dedup_id, _ = coordinator.create_escalation(esc_dup)
    checks["duplicate_deduplicated"] = created_dup is False and dedup_id == "esc_g_subprocess_2_after_resolution"

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
