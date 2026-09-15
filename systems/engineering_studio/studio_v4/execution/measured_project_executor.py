"""Measured Project Executor — honest replacement for the v3 AutonomousProjectExecutor.

Phase 1 audit found that ``studio_v3/execution/autonomous_project_executor.py``
fabricated its results: ``_implement`` set ``code_generated = True`` without
writing any code, ``_test`` hardcoded ``coverage = 0.95`` regardless of
whether any test ever ran, and ``_measure_coverage`` returned the same
constant 0.95 unconditionally.

Phase 2 Stream B decision (documented in the accompanying audit report,
``docs/superpowers/specs/2026-08-16-phase2-streamB-audit-report.md``): pivot
to the **measured-work pattern** (Option B) rather than build a real code
generator (Option A). Rationale:

1. The daemon's ``measure_directive_backlog`` / ``audit_historical_log``
   pattern (see ``studio_v3/observatory/resource_economics.py`` and
   ``independent_auditor.py``) already establishes the house style for this
   codebase: every number must come from a real syscall, subprocess, or file
   read — never a hardcoded literal.
2. A real autonomous code generator capable of producing genuinely useful,
   passing code across arbitrary "projects" is a multi-week research effort
   in its own right, and doing it badly would just create a new, subtler
   form of fabrication (plausible-looking but untested/wrong code repeatedly
   marked "passing").
3. What Phase 2 actually needs from the executor is a component whose
   *every claim is independently checkable*. A measurement engine (real
   subprocess test runs, real git diffs, real file stats) satisfies that
   requirement completely and immediately, with zero risk of drift back
   into fabrication.

This module performs exactly one execution primitive per cycle: **run a
real test command and record what really happened.** Every field on
``MeasuredExecutionResult`` is either:

- read directly from a subprocess's real return code / stdout, or
- read directly from ``git diff`` / ``git status`` against the real repo, or
- read directly from a `ResourceMeter` measurement of the process itself.

Nothing is a literal constant standing in for unmeasured work.
"""

from __future__ import annotations
from systems.engineering_studio.execution_command_policy import validate_test_command

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from systems.engineering_studio.studio_v3.observatory.evidence_ledger import EvidenceLedger
from systems.engineering_studio.studio_v3.observatory.resource_economics import ResourceMeter


@dataclass
class MeasuredExecutionResult:
    """Result of one measured execution cycle. Every field is real."""

    success: bool
    test_command: list[str]
    test_returncode: int
    test_passed: bool
    stdout_tail: str
    stderr_tail: str
    files_touched: list[str]
    git_diff_stat: str
    resource_cost: dict
    ledger_event_id: Optional[str] = None
    error: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_claim_dict(self) -> dict:
        """The subset of this result an auditor should independently check."""
        return {
            "passed": self.test_passed,
            "returncode": self.test_returncode,
        }


class MeasuredProjectExecutor:
    """Executes and honestly reports on a real test command against a repo.

    This is the Phase 2 replacement for ``AutonomousProjectExecutor``. It
    does not claim to "implement", "document", or "deploy" a project — those
    steps in v3 were fabricated (`_implement` set a flag and did nothing;
    `_deploy` returned `True` unconditionally). Instead it does the one
    thing it can do honestly: run a real command, measure real resource
    cost, and record real, independently-verifiable evidence.
    """

    def __init__(
        self,
        repo_path: str | Path,
        ledger_db_path: Optional[str | Path] = None,
        agent_name: str = "measured_project_executor",
    ):
        self.repo_path = Path(repo_path)
        self.agent_name = agent_name
        if ledger_db_path is None:
            ledger_db_path = Path.cwd() / ".observatory" / "evidence_ledger.sqlite3"
        self._ledger = EvidenceLedger(ledger_db_path)

    def _run(self, command: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
        )

    def _git_diff_stat(self) -> str:
        result = self._run(["git", "diff", "--stat"])
        return result.stdout

    def _git_touched_files(self) -> list[str]:
        """Real, currently-uncommitted files touched in the working tree."""
        result = self._run(["git", "status", "--porcelain"])
        files = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # porcelain format: "XY path" (or "XY orig -> new" for renames)
            path = line.split(" ", 1)[1] if " " in line else line
            files.append(path.split(" -> ")[-1])
        return files

    def execute_test_cycle(self, test_command: list[str]) -> MeasuredExecutionResult:
        """Run `test_command` for real and record honest, checkable evidence.

        `test_command` is caller-supplied (e.g. ["python3", "-m", "pytest",
        "tests/test_x.py", "-q"]) — this executor never invents a command,
        never skips the run, and never overrides the real return code.
        """
        with ResourceMeter(label="measured_test_cycle") as meter:
            try:
                result = self._run(validate_test_command(test_command))
                error = None
                returncode = result.returncode
                stdout = result.stdout
                stderr = result.stderr
            except (OSError, FileNotFoundError) as exc:
                error = str(exc)
                returncode = -1
                stdout = ""
                stderr = ""

        test_passed = error is None and returncode == 0
        files_touched = self._git_touched_files()
        diff_stat = self._git_diff_stat()

        exec_result = MeasuredExecutionResult(
            success=test_passed,
            test_command=test_command,
            test_returncode=returncode,
            test_passed=test_passed,
            stdout_tail=stdout[-2000:],
            stderr_tail=stderr[-2000:],
            files_touched=files_touched,
            git_diff_stat=diff_stat,
            resource_cost=meter.result,
            error=error,
        )

        event_id = self._ledger.record_event(
            agent=self.agent_name,
            action="execute_test_cycle",
            input_data={"test_command": test_command},
            output_data={"stdout_tail": exec_result.stdout_tail, "stderr_tail": exec_result.stderr_tail},
            test_result=exec_result.to_claim_dict(),
            resource_cost=exec_result.resource_cost,
            files_modified=exec_result.files_touched,
        )
        exec_result.ledger_event_id = event_id

        return exec_result

    def measure_repo_state(self) -> dict:
        """Real, non-fabricated snapshot of repo state — no work claimed.

        Used for cycles where there is nothing new to test; still records
        real measurements (file counts, uncommitted changes) rather than
        inventing progress.
        """
        with ResourceMeter(label="measure_repo_state") as meter:
            touched = self._git_touched_files()
            diff_stat = self._git_diff_stat()
            head = self._run(["git", "rev-parse", "HEAD"]).stdout.strip()

        snapshot = {
            "head_commit": head,
            "uncommitted_files": touched,
            "git_diff_stat": diff_stat,
            "resource_cost": meter.result,
        }

        event_id = self._ledger.record_event(
            agent=self.agent_name,
            action="measure_repo_state",
            output_data={"head_commit": head, "uncommitted_files": touched},
            resource_cost=snapshot["resource_cost"],
            git_commit_hash=head,
        )
        snapshot["ledger_event_id"] = event_id
        return snapshot
