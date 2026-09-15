"""End-to-end test for the Observatory integration in continuous_autonomous_daemon.py.

Verifies that AutonomousDaemon._run_observatory_cycle performs real,
evidence-backed self-monitoring work against a temp directives tree (never
the live 67k-file .directives-ingestion) and that a real, non-fabricated
event lands in the Evidence Ledger.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from continuous_autonomous_daemon import AutonomousDaemon  # noqa: E402


@pytest.fixture
def temp_daemon(tmp_path, monkeypatch):
    """Build an AutonomousDaemon wired entirely to temp paths."""
    directives_root = tmp_path / "directives-ingestion"
    for sub in ("pending", "approved", "in-progress", "completed", "rejected"):
        (directives_root / sub).mkdir(parents=True)
    # Give it a couple of real files so backlog counts are non-zero.
    (directives_root / "pending" / "a.yaml").write_text("name: a\n")
    (directives_root / "pending" / "b.yaml").write_text("name: b\n")

    ledger_path = tmp_path / "evidence_ledger.sqlite3"
    execution_log = tmp_path / ".nexus_execution_log.jsonl"

    daemon = AutonomousDaemon(ledger_path=ledger_path)
    daemon.directives_path = directives_root
    daemon.execution_log = execution_log
    return daemon


def test_observatory_cycle_records_real_event_with_nonfabricated_cost(temp_daemon):
    daemon = temp_daemon

    daemon._run_observatory_cycle()

    events = daemon.ledger.query_events(action="observatory_self_monitoring_cycle")
    assert len(events) == 1

    event = events[0]
    resource_cost = event["resource_cost"]
    assert resource_cost is not None
    assert resource_cost["wall_seconds"] > 0
    assert resource_cost["cpu_seconds"] >= 0
    assert resource_cost["process_lifetime_peak_rss_kb"] > 0

    # No source changes were made by this cycle -> no invented files/commit.
    assert event["files_modified"] is None
    assert event["git_commit_hash"] is None

    output_data = event["output_data"]
    backlog = output_data["directive_backlog"]
    assert backlog["subdirs"]["pending"]["file_count"] == 2
    assert backlog["subdirs"]["approved"]["file_count"] == 0

    # Chain integrity: the recorded event must be verifiable, not just present.
    is_valid, bad_event_id = daemon.ledger.verify_chain()
    assert is_valid, f"ledger chain broken at {bad_event_id}"


def test_observatory_cycle_runs_historical_audit_every_n_cycles(temp_daemon):
    daemon = temp_daemon
    daemon.OBSERVATORY_AUDIT_EVERY_N_CYCLES = 3

    # Seed a real (temp) execution log with a fabrication-signature pattern:
    # the same code_lines value repeated for one directive.
    with open(daemon.execution_log, "w") as f:
        for _ in range(6):
            f.write(json.dumps({"directive": "X", "code_lines": 42, "status": "COMPLETE"}) + "\n")

    for _ in range(3):
        daemon._run_observatory_cycle()

    events = daemon.ledger.query_events(action="observatory_self_monitoring_cycle")
    assert len(events) == 3

    audited = [e for e in events if "historical_log_audit" in e["output_data"]]
    assert len(audited) == 1
    verdict = audited[0]["output_data"]["historical_log_audit"]
    assert "verdict" in verdict
    assert verdict["entries_analyzed"] == 6
