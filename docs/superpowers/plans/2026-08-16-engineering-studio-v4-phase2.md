# Plan: Engineering Studio v4 Phase 2 — Storage Optimization & Autonomous Audit Loop

**Spec:** docs/superpowers/specs/2026-08-16-engineering-studio-v4-phase2-spec.md  
**Scope:** Three parallel work streams (independent, no conflicts)  
**Repo:** ${NEXUS_ROOT}, branch main  
**Parallel Dispatch:** All three streams via dispatching-parallel-agents  

---

## Work Stream A: Storage Tier Implementation

### Task A1: Tier Manager Core
- Implement `systems/engineering_studio/studio_v4/storage/tiered_storage.py`
- Classes: `TierManager`, `TierConfig`, `FileDescriptor`
- Methods: `classify_file(path) -> tier`, `get_tier_config(tier) -> TierConfig`, `should_migrate(file) -> bool`
- Tests: file classification logic, tier configuration loading
- Integration: record all measurements in Observatory (ResourceMeter)

### Task A2: Compression Pipeline
- Implement `systems/engineering_studio/studio_v4/storage/compression_pipeline.py`
- Classes: `CompressionPipeline`, `CompressionStrategy`
- Strategies: gzip (JSON/text), zip (mixed), sqlite3.gz (databases)
- Methods: `compress(file) -> compressed_path`, `decompress_jit(archive, target_file) -> data`
- Tests: compression ratio validation, JIT decompression accuracy
- Measure: before/after sizes via ResourceMeter

### Task A3: Lifecycle Manager & Daemon
- Implement `systems/engineering_studio/studio_v4/storage/lifecycle_manager.py`
- Classes: `LifecycleManager`, `MigrationScheduler`
- Methods: `migrate_aged_files(days: int)`, `migrate_sized_files(percent_full: float)`, `run_cycle()`
- Integration: schedule via cron or APScheduler
- Tests: age-based migration, size-based migration, cycle execution
- Record all migrations in Observatory (what moved, size change, compression ratio)

### Task A4: Storage Tier Tests & Integration
- Tests: `tests/test_tiered_storage.py`, `test_compression_pipeline.py`, `test_lifecycle_manager.py`
- Integration test: end-to-end tier movement (create file → age it → migrate → verify in Tier 2 → compress → verify in Tier 3)
- Measurement: current storage state (270GB baseline) → project reduction after tiering
- Commit: all Stream A code + tests

---

## Work Stream B: Executor Repair

### Task B1: Executor Audit & Decision
- Read original `AutonomousProjectExecutor` design specification
- Trace actual behavior: what code is being generated? (Answer: nothing real)
- Decision document: (a) implement real code gen, or (b) pivot to measured-work pattern like daemon's current approach
- Decision: [TBD by implementer based on executor design vs. feasibility]

### Task B2: Implement Executor Repair (Option A path)
*If decision is "real code generation":*
- Modify `AutonomousProjectExecutor._implement` to do real work (small, verifiable changes)
- Modify `AutonomousProjectExecutor._test` to run real tests and capture real results
- Every claim (code_lines, test_result, files_modified) must be **independently verifiable by IndependentAuditor**
- Record work in Observatory: `files_modified` from git diff, `test_result` from subprocess stdout

### Task B2 (Option B path)
*If decision is "pivot to measured-work":*
- Modify executor's work definition to perform real, auditable operations (like daemon's current measure_directive_backlog + audit_historical_log)
- Every cycle: real filesystem/log inspection, real measurement, real recording
- Record work in Observatory

### Task B3: Executor Verification
- Write tests: `tests/test_executor_honesty.py`
- Core test: run executor, capture evidence, run `IndependentAuditor.verify_test_result` on the claimed work
- Verdict: claims must match reality (passed test = test actually ran and passed, etc.)
- Measurement: before/after executor behavior audit via `IndependentAuditor`

### Task B4: Executor Repair Commit
- Implement chosen path (A or B)
- All tests passing
- Audit verdict: **NOT FABRICATED** on executor work
- Commit: all Stream B code + tests + audit report

---

## Work Stream C: 24-Hour Audit Loop

### Task C1: Scheduler & Orchestration
- Implement `systems/engineering_studio/studio_v4/audit_loop/scheduler.py`
- Class: `AuditScheduler` (24h interval using APScheduler or native cron)
- Method: `schedule_audit_cycle()`, `run_audit_cycle()`
- Integration: wires to daemon's Observatory ledger
- Tests: schedule timing, cycle execution

### Task C2: Daily Auditor Logic
- Implement `systems/engineering_studio/studio_v4/audit_loop/daily_auditor.py`
- Class: `DailyAuditor`
- Method: `audit_last_24h() -> verdict` (calls `IndependentAuditor.audit_historical_log` on last 24h of events)
- Records verdict in Observatory as a meta-event (auditor's own evidence)
- Tests: verdict recording, historical log filtering

### Task C3: Alert Handler
- Implement `systems/engineering_studio/studio_v4/audit_loop/alert_handler.py`
- Class: `AlertHandler`
- Methods: `check_verdict_change()`, `fire_alert(previous_verdict, current_verdict)`
- Alerts: if verdict flips to FABRICATED, or if consistency drops
- Integration: log alerts to Observatory + stdout/email (configurable)
- Tests: verdict change detection, alert firing

### Task C4: Daily Reports & Archival
- Implement daily evidence report generation: `audit_loop/daily_report.py`
- Report includes: 24h event count, verdict, any alerts, recommendations
- Archival: reports moved to Tier 3 (cold archive) after 30 days
- Integration: reports linked from Observatory
- Tests: report generation, archival movement

### Task C5: Audit Loop Tests & Cron Setup
- Tests: `tests/test_audit_loop.py` (schedule, auditor, alerts, reports)
- Cron/scheduler config: execute audit cycle daily at fixed time (e.g., 00:00 UTC)
- Integration test: run daemon for 48h with audit loop, verify verdicts are stable + recorded
- Commit: all Stream C code + tests + cron config

---

## Global Constraints (carry from Phase 1)

- All new code under `systems/engineering_studio/studio_v4/`
- Every subsystem records to Observatory (ResourceMeter for measurements)
- Every claim verified by IndependentAuditor (no self-reporting)
- Backward compatibility: legacy `.nexus_execution_log.jsonl` untouched
- Python 3.11+, stdlib + existing dependencies only (no new external packages without justification)

---

## Integration & Verification (after all streams complete)

1. Merge all three streams into main (should be no conflicts)
2. Run full test suite: all Phase 1 (18) + all Phase 2 (15-20) tests
3. Run 48-hour integration test:
   - Daemon runs with all three streams live
   - Storage tiering active (files aging and migrating)
   - Executor doing real work (Stream B repair)
   - Audit loop running every 24h (Stream C)
4. Audit the 48-hour evidence:
   - Check that executor work verdict is NOT FABRICATED
   - Check that storage actually migrated (Tier 1 → Tier 2 → Tier 3)
   - Check that audit verdicts are stable
5. Measure resource consumption: CPU, memory, storage I/O (all via ResourceMeter)
6. Final grade: A+ if all systems green + efficient + honest

---

## Success Criteria (per stream)

**Stream A (Storage):**
- ✅ Files correctly classified to tiers based on age/size
- ✅ Compression achieves 60-70% ratio (measured)
- ✅ Tier migration completes without data loss
- ✅ All measurements in Observatory (ResourceMeter)

**Stream B (Executor):**
- ✅ Executor work is real and auditable
- ✅ IndependentAuditor verdict: NOT FABRICATED
- ✅ Every claim (code_lines, test_result, files_modified) matches reality
- ✅ All tests passing

**Stream C (Audit Loop):**
- ✅ Audit runs every 24 hours reliably
- ✅ Verdict recorded in Observatory
- ✅ Alerts fire if verdict changes
- ✅ Daily reports generated and archived
- ✅ 48-hour test shows stable, verifiable operation

---

## Parallel Dispatch Strategy

All three streams dispatched simultaneously via `dispatching-parallel-agents`:
- Stream A implementer: "Storage Tier Implementation"
- Stream B implementer: "Executor Fabrication Repair"
- Stream C implementer: "24-Hour Audit Loop"

Each gets focused, complete task scope. No dependencies between them. Each records to shared Observatory (no conflicts — different subsystems, different event types).

**Expected wall-clock time:** 2-4 hours (all three running in parallel)  
**Expected commits:** 15-20 total across three streams  
**Expected tests:** 15-20 new tests + 18 Phase 1 tests all passing

---

## Afterward: 24-Hour Autonomous Run

Once Phase 2 is complete:
1. Start the daemon with all systems live
2. Let it run for 48 hours unattended
3. Audit the evidence: does it all check out?
4. If verdicts stable + honest + efficient = Phase 2 COMPLETE with A+ grade

**Then: Ship Engineering Studio v4.** 🚀
