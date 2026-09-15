#!/usr/bin/env python3
"""F10D: isolated-process Engineering Studio worker.

Runs a single bounded A0/A1 read-only verification command through the
existing, unmodified measured_project_executor -- in its own interpreter,
isolated from nexus_federation's and other institutions' namespaces.

Usage: engineering_studio_worker.py <federation_store_path> <delegation_id> <mission_id> <command_json>
  command_json: a JSON array, e.g. ["sqlite3", "<path>", "PRAGMA integrity_check;"]
Prints one JSON line: {"report_id": ..., "success": ...}
"""
import sys
import json
import tempfile

NEXUS_ROOT = "${NEXUS_ROOT}"
sys.path.insert(0, NEXUS_ROOT)


def main():
    store_path, delegation_id, mission_id, command_json = sys.argv[1:5]
    command = json.loads(command_json)

    from systems.engineering_studio.studio_v4.execution.measured_project_executor import MeasuredProjectExecutor

    executor = MeasuredProjectExecutor(
        repo_path=NEXUS_ROOT, ledger_db_path=tempfile.mktemp(suffix=".sqlite3"),
    )
    measured_result = executor.execute_test_cycle(command)

    FEDERATION_ROOT = f"{NEXUS_ROOT}/systems/nexus_federation"
    sys.path.append(FEDERATION_ROOT)  # append, not insert -- no `runtime` collision (studio's own package is `systems.engineering_studio.*`, fully qualified, never bare `runtime`), but keep consistent lowest-priority convention

    from runtime.adapters.engineering_studio_adapter import build_report_from_measured_result
    from persistence.db import FederationStore

    report_id = f"{delegation_id}-report"
    payload = build_report_from_measured_result(measured_result, cycle_id=report_id)
    payload["mission_id"] = mission_id

    store = FederationStore(store_path)
    store.log_institutional_report(
        institution_id="engineering_studio", mission_id=mission_id, report_id=report_id, payload=payload,
    )

    print(json.dumps({
        "report_id": report_id,
        "success": measured_result.success,
        "git_diff_stat": measured_result.git_diff_stat,
    }))


if __name__ == "__main__":
    main()
