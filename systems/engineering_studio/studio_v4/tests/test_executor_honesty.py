"""Verify MeasuredProjectExecutor's claims match reality (Phase 2 Stream B).

Core requirement: whatever the executor claims (test passed/failed,
resource cost, files touched) must be independently reproducible by
IndependentAuditor re-running the same real command, not merely
self-reported.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
_V4_DIR = _THIS_DIR.parent
_SYSTEMS_DIR = _V4_DIR.parent.parent
if str(_SYSTEMS_DIR) not in sys.path:
    sys.path.insert(0, str(_SYSTEMS_DIR))

from engineering_studio.studio_v4.execution.measured_project_executor import MeasuredProjectExecutor  # noqa: E402
from engineering_studio.studio_v3.observatory.independent_auditor import IndependentAuditor  # noqa: E402
from engineering_studio.studio_v3.observatory.evidence_ledger import EvidenceLedger  # noqa: E402

REPO_ROOT = _V4_DIR.parent.parent.parent  # .../NEXUS


@pytest.fixture
def tmp_ledger_path(tmp_path):
    return tmp_path / "evidence_ledger.db"


@pytest.fixture
def passing_test_file(tmp_path):
    f = tmp_path / "test_always_passes.py"
    f.write_text("def test_trivially_true():\n    assert 1 + 1 == 2\n")
    return f


@pytest.fixture
def failing_test_file(tmp_path):
    f = tmp_path / "test_always_fails.py"
    f.write_text("def test_trivially_false():\n    assert 1 == 2\n")
    return f


def test_passing_cycle_claim_matches_independent_rerun(tmp_ledger_path, passing_test_file):
    executor = MeasuredProjectExecutor(repo_path=REPO_ROOT, ledger_db_path=tmp_ledger_path)
    command = [sys.executable, "-m", "pytest", str(passing_test_file), "-q"]

    result = executor.execute_test_cycle(command)

    assert result.test_passed is True
    assert result.test_returncode == 0
    assert result.ledger_event_id is not None

    auditor = IndependentAuditor()
    verdict = auditor.verify_test_result(
        claimed_result=result.to_claim_dict(),
        test_command=command,
        cwd=REPO_ROOT,
    )

    assert verdict["verified"] is True
    assert verdict["actual_passed"] is True


def test_failing_cycle_claim_matches_independent_rerun(tmp_ledger_path, failing_test_file):
    executor = MeasuredProjectExecutor(repo_path=REPO_ROOT, ledger_db_path=tmp_ledger_path)
    command = [sys.executable, "-m", "pytest", str(failing_test_file), "-q"]

    result = executor.execute_test_cycle(command)

    assert result.test_passed is False
    assert result.test_returncode != 0

    auditor = IndependentAuditor()
    verdict = auditor.verify_test_result(
        claimed_result=result.to_claim_dict(),
        test_command=command,
        cwd=REPO_ROOT,
    )

    assert verdict["verified"] is True
    assert verdict["actual_passed"] is False


def test_executor_never_claims_pass_without_a_real_run(tmp_ledger_path, failing_test_file):
    """Regression guard for the v3 bug: coverage/pass claims must originate
    from a real subprocess result, not a hardcoded literal."""
    executor = MeasuredProjectExecutor(repo_path=REPO_ROOT, ledger_db_path=tmp_ledger_path)
    command = [sys.executable, "-m", "pytest", str(failing_test_file), "-q"]

    result = executor.execute_test_cycle(command)

    # The v3 fabrication bug: _test() hardcoded coverage=0.95 and returned
    # True regardless of the failing test. Here the claim must reflect the
    # real non-zero returncode.
    assert result.test_returncode != 0
    assert result.success is False


def test_resource_cost_is_real_measurement_not_constant(tmp_ledger_path, passing_test_file):
    executor = MeasuredProjectExecutor(repo_path=REPO_ROOT, ledger_db_path=tmp_ledger_path)
    command = [sys.executable, "-m", "pytest", str(passing_test_file), "-q"]

    r1 = executor.execute_test_cycle(command)
    r2 = executor.execute_test_cycle(command)

    for r in (r1, r2):
        assert r.resource_cost["wall_seconds"] > 0
        assert r.resource_cost["label"] == "measured_test_cycle"

    # Wall-clock timings of two independent subprocess runs should not be
    # bit-identical constants (that pattern is exactly what
    # IndependentAuditor.audit_historical_log flags as fabrication).
    assert r1.resource_cost["wall_seconds"] != r2.resource_cost["wall_seconds"]


def test_ledger_events_are_independently_readable_and_chain_verifies(tmp_ledger_path, passing_test_file):
    executor = MeasuredProjectExecutor(repo_path=REPO_ROOT, ledger_db_path=tmp_ledger_path)
    command = [sys.executable, "-m", "pytest", str(passing_test_file), "-q"]

    result = executor.execute_test_cycle(command)

    ledger = EvidenceLedger(tmp_ledger_path)
    stored = ledger.get_event(result.ledger_event_id)
    assert stored is not None
    assert stored["test_result"]["passed"] is True
    assert stored["action"] == "execute_test_cycle"

    chain_ok, bad_event = ledger.verify_chain()
    assert chain_ok is True
    assert bad_event is None


def test_measure_repo_state_records_real_git_head(tmp_ledger_path):
    executor = MeasuredProjectExecutor(repo_path=REPO_ROOT, ledger_db_path=tmp_ledger_path)
    snapshot = executor.measure_repo_state()

    real_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True
    ).stdout.strip()

    assert snapshot["head_commit"] == real_head
    assert snapshot["ledger_event_id"] is not None
