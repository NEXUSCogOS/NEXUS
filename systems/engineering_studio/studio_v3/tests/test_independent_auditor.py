"""Tests for IndependentAuditor — verification against real ground truth."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)

from observatory.independent_auditor import IndependentAuditor

REAL_LOG_PATH = "${NEXUS_ROOT}/.nexus_execution_log.jsonl"


def _run_git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True, check=True
    )


@pytest.fixture
def temp_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(["init"], repo)
    _run_git(["config", "user.email", "test@test.com"], repo)
    _run_git(["config", "user.name", "Test"], repo)

    file_a = repo / "a.txt"
    file_a.write_text("initial\n")
    _run_git(["add", "a.txt"], repo)
    _run_git(["commit", "-m", "initial commit"], repo)

    since_commit = _run_git(["rev-parse", "HEAD"], repo).stdout.strip()

    file_b = repo / "b.txt"
    file_b.write_text("second file\n")
    _run_git(["add", "b.txt"], repo)
    _run_git(["commit", "-m", "add b.txt"], repo)

    return repo, since_commit


class TestVerifyFilesModified:
    def test_discrepancy_when_claim_includes_fabricated_file(self, temp_git_repo):
        repo, since_commit = temp_git_repo
        auditor = IndependentAuditor()

        result = auditor.verify_files_modified(
            claimed_files=["b.txt", "nonexistent_fabricated.txt"],
            since_commit=since_commit,
            repo_path=repo,
        )

        assert result["verified"] is False
        assert "nonexistent_fabricated.txt" in result["discrepancy"]
        assert "b.txt" in result["actually_changed"]

    def test_verified_when_claim_matches_reality(self, temp_git_repo):
        repo, since_commit = temp_git_repo
        auditor = IndependentAuditor()

        result = auditor.verify_files_modified(
            claimed_files=["b.txt"],
            since_commit=since_commit,
            repo_path=repo,
        )

        assert result["verified"] is True
        assert result["discrepancy"] == []


class TestVerifyTestResult:
    def test_passing_test_verified_true(self, tmp_path):
        test_file = tmp_path / "test_pass.py"
        test_file.write_text("def test_ok():\n    assert True\n")

        auditor = IndependentAuditor()
        result = auditor.verify_test_result(
            claimed_result={"passed": True},
            test_command=[sys.executable, "-m", "pytest", str(test_file), "-v"],
            cwd=tmp_path,
        )

        assert result["actual_passed"] is True
        assert result["verified"] is True

    def test_false_claim_on_failing_test_verified_false(self, tmp_path):
        test_file = tmp_path / "test_fail.py"
        test_file.write_text("def test_bad():\n    assert False\n")

        auditor = IndependentAuditor()
        result = auditor.verify_test_result(
            claimed_result={"passed": True},
            test_command=[sys.executable, "-m", "pytest", str(test_file), "-v"],
            cwd=tmp_path,
        )

        assert result["actual_passed"] is False
        assert result["verified"] is False


class TestAuditHistoricalLog:
    def test_mixed_fixture(self, tmp_path):
        log_file = tmp_path / "fixture.jsonl"
        lines = []

        # 3 directives x 5 entries each, constant code_lines per directive
        constant_directives = {
            "directive_alpha": 120,
            "directive_beta": 45,
            "directive_gamma": 300,
        }
        for name, value in constant_directives.items():
            for _ in range(5):
                lines.append(
                    json.dumps(
                        {
                            "timestamp": "2026-01-01T00:00:00",
                            "directive": name,
                            "status": "completed",
                            "code_lines": value,
                            "coverage": 80,
                            "audit_approved": True,
                            "deployed": True,
                        }
                    )
                )

        # 4th directive, genuinely varying code_lines
        varying_values = [10, 55, 132, 47, 88]
        for value in varying_values:
            lines.append(
                json.dumps(
                    {
                        "timestamp": "2026-01-01T00:00:00",
                        "directive": "directive_delta",
                        "status": "completed",
                        "code_lines": value,
                        "coverage": 80,
                        "audit_approved": True,
                        "deployed": True,
                    }
                )
            )

        log_file.write_text("\n".join(lines) + "\n")

        auditor = IndependentAuditor()
        result = auditor.audit_historical_log(log_file, sample_size=1000)

        assert result["entries_analyzed"] == 20
        assert result["unique_directives"] == 4
        assert result["directives_with_constant_code_lines"] == 3
        assert result["directives_with_variable_code_lines"] == 1
        assert result["verdict"] == "MIXED"

        assert result["evidence"]["directive_alpha"]["constant"] is True
        assert result["evidence"]["directive_delta"]["constant"] is False

    def test_audit_real_execution_log(self):
        """Integration-style test against the real execution log.

        Does not assert a specific verdict value (log format/content may
        evolve) but asserts the function runs cleanly and returns a
        well-formed dict. Prints the actual verdict — this is evidence
        cited by the Task 4 baseline report.
        """
        if not Path(REAL_LOG_PATH).exists():
            pytest.skip(f"real execution log not found at {REAL_LOG_PATH}")

        auditor = IndependentAuditor()
        result = auditor.audit_historical_log(REAL_LOG_PATH, sample_size=1000)

        assert result["entries_analyzed"] == 1000
        assert isinstance(result["unique_directives"], int)
        assert isinstance(result["directives_with_constant_code_lines"], int)
        assert isinstance(result["directives_with_variable_code_lines"], int)
        assert result["verdict"] in ("LIKELY_FABRICATED", "LIKELY_REAL", "MIXED")
        assert isinstance(result["evidence"], dict)

        print("\n=== audit_historical_log REAL LOG RESULT ===")
        print(f"entries_analyzed: {result['entries_analyzed']}")
        print(f"unique_directives: {result['unique_directives']}")
        print(
            f"directives_with_constant_code_lines: "
            f"{result['directives_with_constant_code_lines']}"
        )
        print(
            f"directives_with_variable_code_lines: "
            f"{result['directives_with_variable_code_lines']}"
        )
        print(f"VERDICT: {result['verdict']}")
        print("=============================================")
