# Spec: Engineering Studio v4 — Research-Grade Autonomous Engineering Intelligence

Source: user master directive, 2026-08-16 ("ENGINEERING STUDIO v4 — RESEARCH GRADE
AUTONOMOUS ENGINEERING INTELLIGENCE SYSTEM"). This file is the verbatim-intent
authority for the Phase 1 plan. Full original directive is preserved in the
conversation; this spec extracts the binding requirements for Phase 1.

## Binding requirement (from prior-turn audit finding)

An audit this session established that Engineering Studio v3's execution log
(`.nexus_execution_log.jsonl`, 2,766,535 entries) reports fabricated metrics:
each of ~8 recurring directive templates writes a constant `code_lines` value
(e.g. always exactly 125, 128, 148...) regardless of actual work performed,
and cross-referencing against the filesystem showed 0 real source files
created corresponding to "completions." This spec's Phase 1 exists
specifically to replace that pattern with verifiable evidence.

## Operating principle (binding)

> Evidence > Claims. Measurement > Assumption. Efficiency > Volume.
> Quality > Quantity. Scientific validation > Self-reporting.

Every metric produced by Phase 1 subsystems MUST be independently
reproducible: computed from a query against real, inspectable state
(filesystem stat, git log, subprocess resource usage — not a hardcoded
constant, not a self-report with no underlying computation).

## Phase 1 scope (this plan)

Phase 1 builds the minimum evidence infrastructure needed before any further
"development" work is trusted:

1. **Evidence Ledger** — immutable, hash-chained SQLite event log recording
   every autonomous action with: event_id, timestamp (UTC), agent, action,
   input, output, test_result, resource_cost, files_modified, git_commit_hash,
   verification_status, and a SHA-256 hash of the record chained to the prior
   record's hash (tamper-evident, not merely tamper-resistant).
2. **Resource Economics Engine** — measures real CPU seconds, wall-clock time,
   peak RSS memory, and bytes written for a given unit of work, using
   `resource.getrusage` / `time.process_time` / actual `os.stat` deltas —
   never estimates or fixed constants.
3. **Independent Auditor** — a validation module that takes a claim (e.g. "N
   files were modified", "test X passed") and independently verifies it
   against ground truth (`git diff --stat`, re-running the named test, `os.stat`
   mtimes) without trusting the claimant's self-report. Must be able to
   process the existing `.nexus_execution_log.jsonl` and produce a verdict on
   what fraction of historical claims are independently verifiable.
4. **Baseline Academic Assessment** — a generated report at
   `research/engineering_studio/architecture/baseline_assessment.md`
   reproducing the "Evidence vs Architecture" table from the master
   directive, with every grade backed by a citation to a specific measured
   number (not asserted).

## Global Constraints

- No destructive operations on existing data (`.nexus_execution_log.jsonl`,
  `.directives-ingestion/`) — Phase 1 reads and analyzes; it does not delete,
  move, or truncate. Compression/rotation from the resource-economics turn
  remains explicitly deferred pending separate user confirmation.
- All new code lives under `systems/engineering_studio/studio_v3/observatory/`
  (new subsystem — "Engineering Observatory" per the master directive's
  architecture diagram) to keep it addressable and separable from the
  existing (untrusted) `execution/` output-generation code.
- Every subsystem ships with real unit tests that exercise it against real
  filesystem/git/process state — not mocks that assert the code returns
  whatever it was told to return.
- Python 3.11+, stdlib preferred (`sqlite3`, `hashlib`, `resource`, `subprocess`)
  — no new external dependencies unless a task explicitly justifies one.
- Working directly on `main` (user's explicit choice this session — no
  worktree isolation). Commit after each task.

## Out of scope for Phase 1

Storage tier migration (Tier 1/2/3 physical data movement), Compression
Intelligence Engine, Librarian feedback-loop wiring, 30-day validation
program, full benchmark comparison against external systems. These are
Phase 2+ and depend on Phase 1's evidence infrastructure existing first.
