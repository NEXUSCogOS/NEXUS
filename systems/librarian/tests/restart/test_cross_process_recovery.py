"""REAL cross-process, cross-institution recovery test (F3 mission
section 22): repeats the F2 process-boundary standard for the real
Librarian path.

    NEXUS process (A)  -> delegation persisted -> exits
    Librarian process (B) -> receives, executes, reports -> exits
    NEXUS process (C, new) -> consumes report, reconstructs state

Three genuinely separate OS processes (subprocess.run), no shared Python
objects across any of them -- only the shared SQLite file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

FEDERATION_ROOT = str(Path(__file__).resolve().parents[3] / "nexus_federation")
DAT_AI_ROOT = str(Path(__file__).resolve().parents[3] / "dat_ai")
LIBRARIAN_ROOT = str(Path(__file__).resolve().parents[2])
HELPERS_DIR = Path(__file__).resolve().parent / "_subprocess_helpers"


def _run_helper(script: str, args: list[str]) -> dict:
    env = dict(os.environ)
    env["FEDERATION_ROOT"] = FEDERATION_ROOT
    env["DAT_AI_ROOT"] = DAT_AI_ROOT
    env["LIBRARIAN_ROOT"] = LIBRARIAN_ROOT
    proc = subprocess.run(
        [sys.executable, str(HELPERS_DIR / script), *args],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert proc.returncode == 0, f"{script} failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_real_cross_process_cross_institution_recovery(tmp_path, real_data_dir):
    db_path = tmp_path / "cross_process.db"

    # --- PROCESS A: NEXUS ---
    result_a = _run_helper("process_a_nexus.py", [str(db_path)])
    assert result_a["accepted"] is True
    assert result_a["delegation_count"] == 1
    pid_a = result_a["pid"]
    delegation = result_a["delegation"]

    # --- PROCESS B: Librarian (genuinely separate OS process) ---
    result_b = _run_helper("process_b_librarian.py", [str(db_path), str(real_data_dir)])
    assert result_b["executed_count"] == 1
    pid_b = result_b["pid"]
    assert pid_b != pid_a
    librarian_report = result_b["report"]
    assert librarian_report["institution"] == "librarian"

    report_path = tmp_path / "librarian_report.json"
    report_path.write_text(json.dumps(librarian_report))

    # --- PROCESS C: NEXUS again, a THIRD distinct process ---
    result_c = _run_helper(
        "process_c_nexus.py",
        [str(db_path), str(report_path), delegation["provenance_id"]],
    )
    pid_c = result_c["pid"]
    assert pid_c != pid_a
    assert pid_c != pid_b
    assert result_c["accepted"] is True
    assert result_c["institutions_in_registry"] == ["dat_ai", "librarian"]
    assert "delegation_proposal" in result_c["provenance_chain_source_types"]
    assert result_c["provenance_chain_length"] >= 3

    evidence = {
        "pid_a_nexus": pid_a,
        "pid_b_librarian": pid_b,
        "pid_c_nexus": pid_c,
        "all_distinct": len({pid_a, pid_b, pid_c}) == 3,
        "institutions_in_final_registry": result_c["institutions_in_registry"],
        "cross_institution_provenance_chain": result_c["provenance_chain_source_types"],
    }
    out_path = Path(os.environ.get("CROSS_PROCESS_EVIDENCE_OUT", tmp_path / "evidence.json"))
    out_path.write_text(json.dumps(evidence, indent=2))
