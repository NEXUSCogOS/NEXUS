#!/usr/bin/env python3
"""PROCESS B: 'Librarian process' -- a genuinely separate OS process from
Process A. Loads the SAME shared federation store, claims the pending
delegation, executes a real bounded research mission, and exits. It never
calls NEXUS's kernel -- only the shared store and its own research
executor, preserving the institutional boundary.

Usage: process_b_librarian.py <db_path> <librarian_data_dir>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.environ["FEDERATION_ROOT"])
sys.path.insert(0, os.environ["LIBRARIAN_ROOT"])

from persistence.db import FederationStore  # noqa: E402
from runtime.delegation_inbox import poll_and_execute  # noqa: E402


def main() -> None:
    db_path = sys.argv[1]
    data_dir = sys.argv[2]
    store = FederationStore(db_path)

    executed = poll_and_execute(store, data_dir=data_dir)
    store.checkpoint()

    print(json.dumps({
        "pid": os.getpid(),
        "executed_count": len(executed),
        "report": executed[0].report if executed else None,
        "proposal_id": executed[0].proposal_id if executed else None,
    }))


if __name__ == "__main__":
    main()
