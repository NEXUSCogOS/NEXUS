#!/usr/bin/env python3
"""PROCESS C: a THIRD, genuinely separate OS process -- a fresh 'NEXUS
process' that consumes Librarian's report and reconstructs full
cross-institution state, proving no in-memory object survived from
Process A or Process B.

Usage: process_c_nexus.py <db_path> <report_json_path> <delegation_provenance_id>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.environ["FEDERATION_ROOT"])
sys.path.insert(0, os.environ["DAT_AI_ROOT"])
sys.path.insert(0, os.environ["LIBRARIAN_ROOT"])

from kernel import FederationKernel  # noqa: E402
from persistence.db import FederationStore  # noqa: E402
from provenance.graph import make_store_lookup, trace_back  # noqa: E402


def main() -> None:
    db_path = sys.argv[1]
    report_json_path = sys.argv[2]
    delegation_provenance_id = sys.argv[3]

    with open(report_json_path) as f:
        report = json.load(f)

    store = FederationStore(db_path)
    kernel = FederationKernel(store)

    result = kernel.ingest_report(report, triggering_provenance_ids=[delegation_provenance_id])
    store.checkpoint()

    lookup = make_store_lookup(store)
    chain = trace_back(result.provenance_ids[0], lookup) if result.provenance_ids else []

    entries = {e["institution_id"]: e for e in store.all_registry_entries()}

    print(json.dumps({
        "pid": os.getpid(),
        "accepted": result.accepted,
        "institutions_in_registry": sorted(entries.keys()),
        "provenance_chain_source_types": [r.source_type for r in chain],
        "provenance_chain_length": len(chain),
    }))


if __name__ == "__main__":
    main()
