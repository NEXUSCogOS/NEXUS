"""Independent auditor: verifies claims against ground truth.

Unlike self-reported status in the execution log, these checks call real
subprocesses (git, pytest) or parse the real log file directly — no
simulated or mocked ground truth.
"""

from __future__ import annotations
from systems.engineering_studio.execution_command_policy import validate_test_command

import json
import subprocess
from collections import defaultdict
from pathlib import Path


class IndependentAuditor:
    """Verifies claims about work done against real, external ground truth."""

    def verify_files_modified(
        self,
        claimed_files: list[str],
        since_commit: str,
        repo_path: str | Path,
    ) -> dict:
        """Verify claimed changed files against real `git diff --stat`."""
        result = subprocess.run(
            ["git", "diff", "--stat", since_commit, "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )

        actually_changed: list[str] = []
        for line in result.stdout.splitlines():
            if "|" not in line:
                continue
            filename = line.split("|", 1)[0].strip()
            if filename:
                actually_changed.append(filename)

        discrepancy = [f for f in claimed_files if f not in actually_changed]
        verified = len(discrepancy) == 0

        return {
            "claimed": claimed_files,
            "actually_changed": actually_changed,
            "verified": verified,
            "discrepancy": discrepancy,
        }

    def verify_test_result(
        self,
        claimed_result: dict,
        test_command: list[str],
        cwd: str | Path,
    ) -> dict:
        """Re-run the real test command and compare against the claim."""
        result = subprocess.run(
            test_command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )

        actual_passed = result.returncode == 0
        claimed_passed = claimed_result.get("passed")
        verified = claimed_passed == actual_passed

        return {
            "claimed": claimed_result,
            "actual_returncode": result.returncode,
            "actual_passed": actual_passed,
            "verified": verified,
        }

    def audit_historical_log(
        self,
        log_path: str | Path,
        sample_size: int = 1000,
    ) -> dict:
        """Check whether `code_lines` is a suspiciously constant value per
        directive across the historical execution log — a signature of
        fabricated (not genuinely measured) reporting.
        """
        entries_by_directive: dict[str, list[int]] = defaultdict(list)
        entries_analyzed = 0

        with open(log_path, "r") as f:
            for i, line in enumerate(f):
                if i >= sample_size:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                directive = entry.get("directive")
                code_lines = entry.get("code_lines")
                if directive is None or code_lines is None:
                    entries_analyzed += 1
                    continue

                entries_by_directive[directive].append(code_lines)
                entries_analyzed += 1

        evidence: dict = {}
        constant_count = 0
        variable_count = 0
        considered = 0

        for directive, values in entries_by_directive.items():
            unique_values = sorted(set(values))
            is_constant = len(unique_values) == 1
            evidence[directive] = {
                "sample_count": len(values),
                "unique_code_lines_values": unique_values,
                "constant": is_constant,
            }
            if len(values) >= 5:
                considered += 1
                if is_constant:
                    constant_count += 1
                else:
                    variable_count += 1

        if considered == 0:
            verdict = "MIXED"
        else:
            fraction_constant = constant_count / considered
            if fraction_constant >= 0.9:
                verdict = "LIKELY_FABRICATED"
            elif constant_count == 0:
                verdict = "LIKELY_REAL"
            else:
                verdict = "MIXED"

        return {
            "entries_analyzed": entries_analyzed,
            "unique_directives": len(entries_by_directive),
            "directives_with_constant_code_lines": constant_count,
            "directives_with_variable_code_lines": variable_count,
            "verdict": verdict,
            "evidence": evidence,
        }
