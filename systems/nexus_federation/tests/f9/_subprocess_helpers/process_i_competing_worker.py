#!/usr/bin/env python3
"""PHASE I: competing-worker test helper.

Both worker processes attempt to claim the SAME already-QUEUED mission at
(as close to) the same time. Exactly one must win; the other must observe
the canonical lease rather than execute duplicate work.

Usage: process_i_competing_worker.py <db_path> <delegation_id> <worker_name>
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
    delegation_id = sys.argv[2]
    worker_name = sys.argv[3]

    store = FederationStore(db_path)
    coordinator = ExecutiveCoordinator(store)

    won, reason = coordinator.claim_mission_atomic(
        delegation_id, f"lease_{worker_name}", worker_name, f"{worker_name} competing claim attempt"
    )

    print(json.dumps({"pid": os.getpid(), "worker_name": worker_name, "won": won, "reason": reason}))


if __name__ == "__main__":
    main()
