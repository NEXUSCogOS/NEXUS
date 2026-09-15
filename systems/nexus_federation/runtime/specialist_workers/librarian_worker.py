#!/usr/bin/env python3
"""F10D: isolated-process Librarian worker.

Runs in its OWN interpreter with ONLY Librarian's directory on sys.path --
never shares a process with nexus_federation's or another institution's
`runtime` package, closing the namespace collision structurally rather than
by import ordering.

Usage: librarian_worker.py <federation_store_path> <delegation_id> <mission_id> <query> <objective>
Prints one JSON line: {"report_id": ..., "operating_state": ..., "findings_count": ...}
"""
import sys
import json

LIBRARIAN_ROOT = "${NEXUS_ROOT}/systems/librarian"
FEDERATION_ROOT = "${NEXUS_ROOT}/systems/nexus_federation"
# LIBRARIAN_ROOT must resolve FIRST for the bare `runtime` package name --
# append (not insert) FEDERATION_ROOT so it's only consulted as a fallback,
# never shadowing librarian's own `runtime.research_executor`.
sys.path.insert(0, LIBRARIAN_ROOT)
sys.path.append(FEDERATION_ROOT)  # needed only for persistence.db (canonical store)


def main():
    store_path, delegation_id, mission_id, query, objective = sys.argv[1:6]

    from runtime.research_executor import execute_research_mission
    report = execute_research_mission(
        mission_id=mission_id, objective=objective, query=query,
        cycle_id=f"{delegation_id}-report",
    )

    from persistence.db import FederationStore
    store = FederationStore(store_path)
    report_id = f"{delegation_id}-report"
    store.log_institutional_report(
        institution_id="librarian", mission_id=mission_id, report_id=report_id,
        payload=report.model_dump(),
    )

    print(json.dumps({
        "report_id": report_id,
        "operating_state": report.operating_state.value,
        "findings_count": len(report.findings),
        "evidence_refs": report.evidence_refs,
    }))


if __name__ == "__main__":
    main()
