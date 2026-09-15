#!/usr/bin/env python3
"""PHASE G PROCESS A: genuine subprocess restart-recovery helper.

Creates policy v1, activates it, creates a policy v2 proposal, creates an
open escalation. Prints os.getpid() and state as JSON. Exits completely.

Usage: process_g_a.py <db_path>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.environ["FEDERATION_ROOT"])
sys.path.insert(0, os.environ["DAT_AI_ROOT"])

from executive.coordinator import ExecutiveCoordinator  # noqa: E402
from executive.governance import (  # noqa: E402
    PolicyVersion,
    PolicyType,
    PolicyVersionStatus,
    Escalation,
    EscalationClass,
    EscalationSeverity,
)
from persistence.db import FederationStore  # noqa: E402


def main() -> None:
    db_path = sys.argv[1]
    store = FederationStore(db_path)
    coordinator = ExecutiveCoordinator(store)

    # Create + activate policy v1
    pv1 = PolicyVersion(
        policy_version_id="pv_g_subprocess_1",
        policy_id="resource_policy_subprocess_test",
        version=1,
        policy_type=PolicyType.RESOURCE,
        configuration={"max_cpu_seconds": 100},
        status=PolicyVersionStatus.DRAFT,
        change_reason="initial version",
    )
    coordinator.create_policy_version(pv1)
    coordinator.activate_policy_version("pv_g_subprocess_1", "resource_policy_subprocess_test")

    # Create policy v2 as a PROPOSED (not activated) draft
    pv2 = PolicyVersion(
        policy_version_id="pv_g_subprocess_2",
        policy_id="resource_policy_subprocess_test",
        version=2,
        policy_type=PolicyType.RESOURCE,
        configuration={"max_cpu_seconds": 150},
        status=PolicyVersionStatus.PROPOSED,
        change_reason="proposed increase based on observed usage",
        supersedes_version_id="pv_g_subprocess_1",
    )
    coordinator.create_policy_version(pv2)

    # Create an open escalation
    esc = Escalation(
        escalation_id="esc_g_subprocess_1",
        escalation_class=EscalationClass.RESOURCE_BUDGET_EXCEEDED,
        reason="mission requested 150 cpu-seconds, ceiling is 100",
        severity=EscalationSeverity.MEDIUM,
        mission_id="mission_g_subprocess_test",
        trigger_id="trigger_g_subprocess_test",
        current_policy_version_id="pv_g_subprocess_1",
    )
    created, escalation_id, reason = coordinator.create_escalation(esc)

    store.checkpoint()

    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "policy_created": True,
                "policy_activated": True,
                "escalation_created": created,
                "escalation_id": escalation_id,
            }
        )
    )


if __name__ == "__main__":
    main()
