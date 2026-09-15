"""REAL subprocess restart-recovery test (F2 mission section 2).

Unlike tests/restart/test_restart_recovery.py (F1, same-process new-object
simulation), this test spawns two genuinely separate OS processes via
`subprocess.run`, with no shared Python objects, no shared memory, and
Process A fully exited before Process B starts. This closes the one
stated limitation in FEDERATION_RECOVERY_TEST_REPORT.md.

Also computes and records the state-database hash before and after, for
FEDERATION_PROCESS_RECOVERY_EVIDENCE.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

FEDERATION_ROOT = str(Path(__file__).resolve().parents[2])
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")
HELPERS_DIR = Path(__file__).resolve().parent / "_subprocess_helpers"


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_helper(script: str, args: list[str]) -> dict:
    env = dict(os.environ)
    env["FEDERATION_ROOT"] = FEDERATION_ROOT
    env["DAT_AI_ROOT"] = DAT_AI_ROOT
    proc = subprocess.run(
        [sys.executable, str(HELPERS_DIR / script), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert proc.returncode == 0, f"{script} failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_real_subprocess_restart_recovery(tmp_path):
    db_path = tmp_path / "subprocess_restart.db"

    # --- PROCESS A ---
    result_a = _run_helper("process_a.py", [str(db_path)])
    assert result_a["accepted"] is True
    assert result_a["delegation_count"] == 1
    assert result_a["total_delegations_in_store"] == 1
    pid_a = result_a["pid"]

    hash_after_a = _hash_file(db_path)
    process_a_timestamp = result_a["registry_entry"]["last_report_timestamp"]

    # --- PROCESS B (genuinely separate OS process, A has fully exited) ---
    result_b = _run_helper("process_b.py", [str(db_path), process_a_timestamp])
    pid_b = result_b["pid"]

    # This IS a true OS process boundary: two distinct PIDs.
    assert pid_a != pid_b

    checks = result_b["checks"]
    assert checks["institution_state_survives"] is True
    assert checks["accepted_cycle_survives"] is True
    assert checks["evidence_links_survive"] is True
    assert checks["temporal_ordering_survives"] is True
    assert checks["duplicate_recognized"] is True
    assert checks["duplicate_delegation_not_generated"] is True
    assert result_b["all_passed"] is True
    assert result_b["total_delegations_in_store"] == 1  # still exactly 1, not 2
    assert result_b["recorded_process_recovery_event"] is True

    hash_after_b = _hash_file(db_path)

    # Record the full evidence set for FEDERATION_PROCESS_RECOVERY_EVIDENCE.md.
    evidence = {
        "pid_a": pid_a,
        "pid_b": pid_b,
        "accepted_cycle_id": "subprocess-cycle-A",
        "recovered_state_matches": result_b["registry_entry"] == result_a["registry_entry"],
        "delegation_count_after_a": result_a["total_delegations_in_store"],
        "delegation_count_after_b": result_b["total_delegations_in_store"],
        "duplicate_suppression_result": checks["duplicate_delegation_not_generated"],
        "state_db_hash_after_process_a": hash_after_a,
        "state_db_hash_after_process_b": hash_after_b,
    }
    evidence_path = Path(os.environ.get("PROCESS_RECOVERY_EVIDENCE_OUT", tmp_path / "evidence.json"))
    evidence_path.write_text(json.dumps(evidence, indent=2))

    assert result_b["registry_entry"] == result_a["registry_entry"]  # no fabricated replacement state
