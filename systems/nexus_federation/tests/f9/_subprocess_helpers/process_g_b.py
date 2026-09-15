#!/usr/bin/env python3
"""PHASE G PROCESS B: genuine subprocess restart-recovery helper.

Fresh interpreter, fresh ExecutiveCoordinator/FederationKernel, same
FederationStore DB file. Recovers active v1, PROPOSED v2, and the open
escalation. Resolves the escalation. Prints os.getpid() and verification
results as JSON. Exits completely.

Usage: process_g_b.py <db_path>
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

    # Recover active v1
    active = coordinator.resolve_active_policy("resource_policy_subprocess_test")
    checks["v1_recovered_active"] = active is not None and active["status"] == "ACTIVE" and active["version"] == 1

    # Recover PROPOSED v2
    history = coordinator.get_policy_version_history("resource_policy_subprocess_test")
    v2 = next((v for v in history if v["version"] == 2), None)
    checks["v2_recovered_proposed"] = v2 is not None and v2["status"] == "PROPOSED"

    # Recover open escalation
    escalation = coordinator.get_escalation("esc_g_subprocess_1")
    checks["escalation_recovered_open"] = escalation is not None and escalation["status"] == "OPEN"

    # Resolve the escalation
    resolve_success, resolve_reason = coordinator.resolve_escalation(
        "esc_g_subprocess_1",
        "RESOLVED",
        {"decision": "approved one-time budget increase", "approved_by": "process_g_b"},
        "process_g_b",
    )
    checks["escalation_resolved"] = resolve_success

    store.checkpoint()

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
