# Phase 2 Stream B — Executor Fabrication Repair — Audit Report

**Date:** 2026-08-16
**Scope:** `systems/engineering_studio/studio_v3/execution/autonomous_project_executor.py` (audited, left in place, superseded) → new `systems/engineering_studio/studio_v4/execution/measured_project_executor.py`

## Task B1: Audit findings

Traced `AutonomousProjectExecutor._run_full_lifecycle`:

| Step | Method | Behavior found |
|---|---|---|
| implement | `_implement` | Sets `project['code_generated'] = True`. No file written, no `CodeGenerator` call. |
| test | `_test` | Sets `project['tests_generated'] = True` and `project['coverage'] = 0.95` — literal constant, no test executed. |
| test (run) | `_run_tests` | Returns `project.get('coverage', 0) >= 0.95`, i.e. always `True` because `_test` just set that literal. |
| coverage | `_measure_coverage` | `return 0.95` — hardcoded, ignores `project` entirely. |
| audit | `_audit` / `_run_audit` | Sets `audit_passed = True`, returns `True` unconditionally. |
| deploy | `_deploy` | Returns `True` unconditionally, no deployment action. |

Every one of these six lifecycle steps returns a fixed truthy/constant value regardless of input. This exactly matches the Phase 1 audit's finding and the fabrication signature `IndependentAuditor.audit_historical_log` is designed to detect (constant `code_lines`/coverage per directive).

`_generate_code` does call a real `CodeGenerator.generate_from_requirements`, but its output is never used by `_implement`, never written to disk, and never tested — it is dead code relative to the lifecycle that actually runs.

## Task B1: Decision — **Option B (measured-work pivot)**

Reasoning:

1. **House style precedent.** Phase 1 already built the honest pattern this codebase uses: `ResourceMeter` (real `perf_counter`/`getrusage` measurements), `measure_directive_backlog` (real `os.scandir`/`os.stat`), and `IndependentAuditor` (real subprocess re-runs, real `git diff`). Stream B should extend this pattern, not introduce a second, inconsistent approach.
2. **Scope honesty.** A general-purpose autonomous code generator that reliably produces correct, tested, deployable code for arbitrary "projects" is a substantial, open-ended research problem. Attempting it under this task's scope risks producing plausible-looking code with silently wrong test claims — a subtler form of the exact fabrication this stream exists to remove.
3. **What Stream B actually needs to deliver** is an executor whose claims are 100% independently verifiable. A measurement/execution primitive that runs a real, caller-supplied test command and reports the real subprocess return code, real git diff, and real resource cost satisfies that requirement completely, with no risk of drift back into fabrication.

`AutonomousProjectExecutor` (v3) is left in place, unmodified, for backward compatibility per the global constraint ("legacy `.nexus_execution_log.jsonl` untouched"). It is superseded by the v4 executor for any new work.

## Task B2: Implementation

New file: `systems/engineering_studio/studio_v4/execution/measured_project_executor.py`

`MeasuredProjectExecutor`:
- `execute_test_cycle(test_command)` — runs the real `test_command` via `subprocess.run`, wraps it in a `ResourceMeter`, reads the real return code, reads real uncommitted files via `git status --porcelain`, reads a real `git diff --stat`, and records everything as one `EvidenceLedger` event. `success`/`test_passed` are derived strictly from `returncode == 0`.
- `measure_repo_state()` — a no-claimed-work measurement cycle: real `git rev-parse HEAD`, real uncommitted-file list, real resource cost. Used when there is nothing to test, so the executor never has to invent progress to report.

No field in `MeasuredExecutionResult` is a literal constant standing in for real work. `to_claim_dict()` exposes only the two fields (`passed`, `returncode`) that `IndependentAuditor.verify_test_result` checks, so the claim surface matches the auditor's verification surface exactly.

## Task B3: Verification

New file: `systems/engineering_studio/studio_v4/tests/test_executor_honesty.py` (6 tests, all passing):

1. `test_passing_cycle_claim_matches_independent_rerun` — runs a real passing pytest file, then `IndependentAuditor.verify_test_result` independently re-runs the same command and confirms `verified is True`.
2. `test_failing_cycle_claim_matches_independent_rerun` — same, with a real failing test; confirms the executor honestly reports failure and the auditor agrees.
3. `test_executor_never_claims_pass_without_a_real_run` — regression guard directly targeting the v3 bug (hardcoded `coverage=0.95`/`True`): asserts a failing run produces `success is False` and a non-zero return code.
4. `test_resource_cost_is_real_measurement_not_constant` — runs two cycles, asserts `wall_seconds` differs between runs (a constant value across runs is exactly the fabrication signature `audit_historical_log` flags).
5. `test_ledger_events_are_independently_readable_and_chain_verifies` — reads the recorded event back from `EvidenceLedger` by ID and verifies the hash chain (`verify_chain()`) is intact.
6. `test_measure_repo_state_records_real_git_head` — confirms `measure_repo_state()`'s claimed HEAD commit matches an independently-run `git rev-parse HEAD`.

```
$ python3 -m pytest systems/engineering_studio/studio_v4/tests/test_executor_honesty.py -q
......                                                                   [100%]
6 passed in 8.59s
```

## Verdict

**NOT FABRICATED.** Every claim `MeasuredProjectExecutor` makes (test pass/fail, resource cost, files touched, HEAD commit) is sourced from a real subprocess or `git` call and is independently reproducible via `IndependentAuditor`, as demonstrated by the passing test suite above.

## Follow-up (out of scope for this stream)

- `AutonomousProjectExecutor` (v3) still exists and is still importable/usable; it has not been deleted or deprecated in code (only superseded in intent). A future stream should either delete it or add a runtime deprecation warning so nothing accidentally re-adopts the fabricated path.
