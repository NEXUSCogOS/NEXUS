# Spec: Engineering Studio v4 Phase 2 — Storage Optimization & Autonomous Audit Loop

**Based on:** Phase 1 completion (Observatory subsystem live and operational)  
**Scope:** Three parallel work streams targeting storage economics, executor honesty, and audit automation

---

## Binding Requirements (from Phase 1 foundation)

- All work must record evidence via the Observatory (EvidenceLedger + ResourceMeter)
- Every claim must be independently verifiable (via IndependentAuditor)
- No fabrication — if work is synthetic/incomplete, document it honestly
- Preserve Phase 1's immutable evidence chain
- Maintain backward compatibility with legacy `.nexus_execution_log.jsonl`

---

## Phase 2 Work Streams

### Work Stream A: Storage Tier Implementation (Independent)

**Goal:** Implement Tier 2/3 automated storage lifecycle per resource-economics design

**Scope:**
- Tier 1: CPU-resident hot memory (1GB limit, keep <7 days old)
- Tier 2: External drive warm storage (50TB, auto-compress files >7 days old)
- Tier 3: iCloud cold archive (unlimited, auto-archive files >90 days old)
- Automated migration daemon (age-based and size-based tier movement)
- Compression pipeline (60-70% target ratios for JSON/code/evidence)

**Deliverables:**
- `systems/engineering_studio/studio_v4/storage/tiered_storage.py` (tier manager)
- `systems/engineering_studio/studio_v4/storage/compression_pipeline.py` (auto compression)
- `systems/engineering_studio/studio_v4/storage/lifecycle_manager.py` (automated movement)
- Tests + integration with Observatory
- Baseline measurement: current storage state (270GB → target 90GB after tiering)

**Success Criteria:**
- 60-70% storage reduction in Tier 2/3 (measured via ResourceMeter)
- Retrieval latency within spec (T1: <10ms, T2: 50-200ms, T3: 1-10s)
- Zero data loss during tier migration

---

### Work Stream B: Executor Repair (Independent)

**Goal:** Replace `AutonomousProjectExecutor._implement/_test` fabrication with real engineering work

**Current Problem:** The executor writes `code_generated=True` and `coverage=0.95` without doing real work. Observable: 0 real files created across 1.2M cycles, constant `code_lines` values per directive.

**Scope:**
1. Audit what the executor was *designed* to do (read original design spec)
2. Decide: (a) implement real code generation + testing, or (b) pivot to real-work alternatives like the daemon's current `measure_directive_backlog` pattern
3. Whichever path: implement, test, verify via IndependentAuditor that the claim matches reality
4. Record evidence in Observatory

**Deliverables:**
- Repair decision document (why option A vs B)
- Modified `AutonomousProjectExecutor` or replacement flow
- Tests validating that claimed work = real work (verified by auditor)
- Audit report: before/after work authenticity

**Success Criteria:**
- IndependentAuditor verdict on new executor work: **NOT FABRICATED** (evidence of real changes)
- Every directive produces real, auditable changes (file modifications, test execution, etc.)

---

### Work Stream C: 24-Hour Audit Loop (Independent)

**Goal:** Automate the daily human-audit cycle: daemon runs autonomously, Claude reviews evidence every 24 hours

**Scope:**
1. Wire the 24-hour schedule (cron job or scheduler)
2. Each cycle: daemon runs N work units, records to Observatory
3. Every 24 hours: Claude automatically invokes `IndependentAuditor.audit_historical_log` on the ledger's last 24h of events
4. Log the verdict (REAL / LIKELY_FABRICATED / MIXED) back into Observatory
5. Alert if verdict changes (e.g., fabrication detected after being clean)
6. Generate daily evidence report for human review

**Deliverables:**
- `systems/engineering_studio/studio_v4/audit_loop/scheduler.py` (24h orchestration)
- `systems/engineering_studio/studio_v4/audit_loop/daily_auditor.py` (Claude's review routine)
- `systems/engineering_studio/studio_v4/audit_loop/alert_handler.py` (anomaly detection)
- Cron/scheduler configuration
- Daily evidence reports (timestamped, archived to Tier 3)

**Success Criteria:**
- Audit runs exactly every 24 hours
- Verdict recorded in Observatory
- Alert fires if fabrication detected
- Reports generated and archived reliably

---

## Parallel Execution Model

These three work streams are **completely independent**:
- Stream A doesn't depend on B or C (storage is orthogonal to work execution)
- Stream B doesn't depend on A or C (executor fix is self-contained)
- Stream C doesn't depend on A or B (audit loop can work with any work type)
- **No shared state** between streams (each records to Observatory independently)
- **No conflicts** (each modifies different subsystems)

**Dispatch strategy:** Launch all three in parallel via `dispatching-parallel-agents`. They complete independently. Then integrate and verify the combined result.

---

## Integration Checkpoint (after all three complete)

1. Verify no conflicts (each stream in its own subsystem)
2. Run full test suite (all 18 Phase 1 tests + all Phase 2 tests)
3. Run the complete system: daemon + audit loop + storage tiering, for 48 hours
4. Audit the 48-hour evidence: should see real work recorded, storage optimized, verdicts stable
5. Grade Phase 2 (A to A+, depending on completeness and audit results)

---

## Global Constraints (carry forward from Phase 1)

- No destructive ops on Phase 1 evidence ledger (it's immutable by design)
- All new code under `systems/engineering_studio/studio_v4/`
- Every claim verified by `IndependentAuditor`
- Real measurements only (no hardcoding, no estimates)
- Backward compatibility with legacy JSONL log

---

## Timeline & Sizing

**Per-stream estimate:** 3-5 tasks each (15-20 commits total)  
**Parallel execution:** All three streams run concurrently  
**Expected duration:** 2-4 hours wall-clock (6-12 hours serial equivalent)  
**Milestone:** Phase 2 complete when all three streams green + 48h integration test passes

---

## Success Definition

Phase 2 is complete when:
- ✅ Storage reduced 60-70% via tiering
- ✅ Executor work is real and auditable
- ✅ 24-hour audit loop runs reliably
- ✅ 48-hour evidence run shows honest, verifiable work
- ✅ All tests passing
- ✅ Grade: A+ (improved efficiency, zero fabrication, fully autonomous)
