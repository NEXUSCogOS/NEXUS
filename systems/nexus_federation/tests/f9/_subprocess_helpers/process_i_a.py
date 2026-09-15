#!/usr/bin/env python3
"""PHASE I PROCESS A: genuine subprocess loop test.

Receives an event, creates canonical mission, advances to QUEUED, claims
lease -- then EXITS WITHOUT COMPLETING (simulating a worker crash after
claim, before result persistence). Prints os.getpid() and state.

Usage: process_i_a.py <db_path>
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.environ["FEDERATION_ROOT"])
sys.path.insert(0, os.environ["DAT_AI_ROOT"])

from executive.coordinator import ExecutiveCoordinator  # noqa: E402
from executive.events import ExecutiveEvent, EventType  # noqa: E402
from persistence.db import FederationStore  # noqa: E402


def main() -> None:
    db_path = sys.argv[1]
    store = FederationStore(db_path)
    coordinator = ExecutiveCoordinator(store)

    event = ExecutiveEvent(
        event_id="event_i_subprocess_crash_test",
        event_type=EventType.INSTITUTION_REPORT,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        source_institution="sentinel",
        subject="crash_recovery_test_signal",
    )
    event_id, is_new, _ = coordinator.ingest_event(event)

    delegation_id, reason = coordinator.process_event_to_mission(
        event_id, attention_accept=True, attention_reason="HIGH_ATTENTION test signal"
    )

    coordinator.advance_to_queued(delegation_id)

    won, claim_reason = coordinator.claim_mission_atomic(
        delegation_id, "lease_process_a_crashed", "process_a_worker", "claimed before crash"
    )

    store.checkpoint()

    # NOTE: process exits here WITHOUT completing the mission -- simulating
    # a worker crash after claim but before result persistence (crash
    # injection boundary: "after claim").

    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "event_id": event_id,
                "delegation_id": delegation_id,
                "claim_won": won,
                "claim_reason": claim_reason,
                "state_at_crash": coordinator.get_mission_state(delegation_id),
            }
        )
    )


if __name__ == "__main__":
    main()
