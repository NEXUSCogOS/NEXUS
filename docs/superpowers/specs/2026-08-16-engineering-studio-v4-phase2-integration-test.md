# Engineering Studio v4 Phase 2: Integration Test Plan & Autonomous Operation

**Date:** 2026-08-16  
**Status:** Phase 2 Complete (all 58 tests passing)  
**Next:** 48-hour autonomous run + 24-hour audit cycle

---

## Phase 2 Completion Summary

### Stream A: Storage Tier Implementation ✅
- **Commit:** 431318b
- **Deliverables:**
  - TierManager (classification based on age/size)
  - CompressionPipeline (gzip, zip, sqlite3.gz)
  - LifecycleManager (age-based + disk-usage-based migration)
  - 27 tests passing (end-to-end hot→warm→cold verified)
- **Measurement:** Baseline 921MB recorded to evidence ledger
- **Status:** Ready for live operation

### Stream B: Executor Fabrication Repair ✅
- **Commit:** a0df455
- **Deliverables:**
  - MeasuredProjectExecutor (real, auditable work)
  - Option B decision rationale (measured-work pivot vs. real code gen)
  - 6 tests passing (all verify claims against ground truth)
- **Verdict:** NOT FABRICATED
- **Status:** Ready for live operation

### Stream C: 24-Hour Audit Loop ✅
- **Commit:** 1ba0dc2
- **Deliverables:**
  - AuditScheduler (24h orchestration via cron/threading.Timer)
  - DailyAuditor (real 24h-windowed audit via IndependentAuditor)
  - AlertHandler (verdict-change detection)
  - DailyReportGenerator (JSON reports, 30-day archival)
  - 25 tests passing (compressed 48h-equivalent integration test)
- **Cron Config:** `0 0 * * * cd ${NEXUS_ROOT} && python3 -m systems.engineering_studio.studio_v4.audit_loop.scheduler`
- **Status:** Ready for live operation

---

## Phase 2 Test Coverage

| Component | Tests | Status |
|---|---:|---|
| Evidence Ledger (Phase 1) | 5 | ✅ PASS |
| Resource Economics (Phase 1) | 5 | ✅ PASS |
| Independent Auditor (Phase 1) | 6 | ✅ PASS |
| Baseline Assessment (Phase 1) | 2 | ✅ PASS |
| Storage Tier (Stream A) | 27 | ✅ PASS |
| Executor Honesty (Stream B) | 6 | ✅ PASS |
| Audit Loop (Stream C) | 25 | ✅ PASS |
| **TOTAL** | **76** | **✅ PASS** |

---

## Starting Autonomous Operation

### Prerequisites
1. All 76 tests passing ✅
2. All three Phase 2 commits in place (431318b, a0df455, 1ba0dc2, + fix b92aa4e) ✅
3. Observatory evidence ledger initialized ✅
4. Tier 2 path exists: `/Volumes/NEXUS/` ✅
5. Tier 3 path: iCloud Drive configured or `/tmp/tier3_archive/` (for testing) ✅

### Command to Start Daemon

```bash
# Run the startup script
bash ${NEXUS_ROOT}/run_autonomous_phase2.sh

# Or manually:
cd ${NEXUS_ROOT}
export AUDIT_LOOP_LEDGER_PATH="${NEXUS_ROOT}/.observatory/evidence_ledger.sqlite3"
export AUDIT_LOOP_REPORTS_DIR="${NEXUS_ROOT}/.observatory/reports"
python3 -m systems.engineering_studio.studio_v3.continuous_autonomous_daemon &
```

### Daemon Behavior (Per Cycle)

Each cycle:
1. **Measure Directive Backlog:** Count pending/approved/completed directives (real filesystem scan)
2. **Record to Observatory:** ResourceMeter (CPU, wall-clock, RAM) + EvidenceLedger (immutable hash-chained entry)
3. **Every 10 cycles:** Run `audit_historical_log` → record verdict to ledger
4. **Storage Lifecycle:** Every N cycles, TierManager migrates aged files (Tier 1 → 2 → 3)
5. **Log to Legacy:** `.nexus_execution_log.jsonl` (for backward compatibility)

**Example cycle output (stderr/daemon.log):**
```
[2026-08-16 13:45:02] Cycle 1: measure_directive_backlog
[2026-08-16 13:45:02] Recorded event_id=1001 (wall_seconds=0.23, peak_rss_kb=45120, files_modified=0)
[2026-08-16 13:45:12] Cycle 2: measure_directive_backlog
[2026-08-16 13:45:12] Recorded event_id=1002 (wall_seconds=0.24, peak_rss_kb=45280, files_modified=0)
...
[2026-08-16 13:46:12] Cycle 10: audit_historical_log (last 10 events)
[2026-08-16 13:46:12] Verdict: LIKELY_REAL (all variable code_lines, no pattern)
[2026-08-16 13:46:12] Recorded meta_event_id=1010 (auditor verdict)
```

### 24-Hour Audit Cycle

**Manual audit (daily, 00:00 UTC or on-demand):**

```bash
# Run one audit cycle
python3 -m systems.engineering_studio.studio_v4.audit_loop.scheduler

# Or let cron run it automatically every 24h
crontab -e
# Add: 0 0 * * * cd ${NEXUS_ROOT} && \
#      AUDIT_LOOP_LEDGER_PATH=${NEXUS_ROOT}/.observatory/evidence_ledger.sqlite3 \
#      AUDIT_LOOP_REPORTS_DIR=${NEXUS_ROOT}/.observatory/reports \
#      python3 -m systems.engineering_studio.studio_v4.audit_loop.scheduler
```

**Audit cycle produces:**
- JSON report: `.observatory/reports/audit_TIMESTAMP_UUID.json` (24h summary, verdict, alerts)
- Alert to stderr/log if verdict changes
- Events recorded to evidence ledger (with auditor's own meta-event)

**Example report:**
```json
{
  "cycle_start_utc": "2026-08-16T00:00:00Z",
  "cycle_end_utc": "2026-08-16T23:59:59Z",
  "events_analyzed": 1440,
  "unique_directives": 42,
  "verdict": "LIKELY_REAL",
  "previous_verdict": "LIKELY_REAL",
  "alert_fired": false,
  "recommendation": "All systems operating normally. Storage tiering active. No fabrication detected.",
  "timestamp": "2026-08-17T00:00:15Z"
}
```

---

## Monitoring the 48-Hour Integration Test

### What to Expect (First 24 Hours)

1. **Daemon steady state:** Cycles every ~10-15 seconds (measure_directive_backlog + record)
2. **Storage activity:** If testing with real Tier 2 (`/Volumes/NEXUS/`), files aged >7 days will begin compressing
3. **Audit loop (first run):** Records baseline verdict to ledger
4. **No alerts:** (unless previous runs detected fabrication, which they shouldn't have)

### What to Expect (Second 24 Hours)

1. **Daemon continues:** No change to cycle pattern
2. **Second audit:** Compares second 24h window to first 24h; expects stable verdict
3. **Compression progress:** Measure actual storage reduction (baseline 921MB → target 60-70%)
4. **Chain integrity:** `verify_chain()` on the evidence ledger confirms no tampering

### Observing Live Daemon

```bash
# Watch daemon logs
tail -f ${NEXUS_ROOT}/.daemon.log

# Query evidence ledger (SQLite)
sqlite3 ${NEXUS_ROOT}/.observatory/evidence_ledger.sqlite3
  > SELECT COUNT(*) as total_events FROM evidence_ledger;
  > SELECT DISTINCT agent, COUNT(*) as count FROM evidence_ledger GROUP BY agent;
  > SELECT * FROM evidence_ledger WHERE created_at > datetime('now', '-24 hours');

# Check audit reports
ls -lh ${NEXUS_ROOT}/.observatory/reports/

# Verify chain integrity (Python)
python3 -c "
from systems.engineering_studio.studio_v3.observatory.evidence_ledger import EvidenceLedger
ledger = EvidenceLedger('${NEXUS_ROOT}/.observatory/evidence_ledger.sqlite3')
is_valid, first_bad_id = ledger.verify_chain()
print(f'Chain valid: {is_valid}')
if not is_valid:
    print(f'First bad event: {first_bad_id}')
"
```

---

## Success Criteria (48-Hour Integration Test)

✅ **Daemon stability:**
- Runs without crashing for 48 hours
- Cycles complete at consistent intervals
- All events recorded to evidence ledger

✅ **Storage tiering:**
- Files correctly classified to Tier 1/2/3 based on age/size
- Compression measurably reduces file sizes (verify before/after in ledger events)
- Tier 2/3 files retrievable without data loss

✅ **Executor honesty:**
- All executor work is real and auditable (measure_directive_backlog, audit_historical_log)
- No constant code_lines pattern detected
- IndependentAuditor.audit_historical_log verdict: LIKELY_REAL (not FABRICATED)

✅ **Audit loop:**
- First 24h: baseline verdict recorded
- Second 24h: verdict stable (same verdict, no alerts)
- Reports generated and archived to Tier 3

✅ **Chain integrity:**
- `EvidenceLedger.verify_chain()` returns `(True, None)` (no tampering)
- Hash chain unbroken across all 2880+ events (48h at ~1 event/second)

---

## Stopping Autonomous Operation

```bash
# Find daemon PID
ps aux | grep continuous_autonomous_daemon

# Stop cleanly
kill <PID>

# Or from run_autonomous_phase2.sh output:
kill <DAEMON_PID>
```

---

## Phase 3: Next Steps (After Successful 48-Hour Run)

If the 48-hour integration test is successful:

1. **Academic grading:** Phase 2 Scientific Assessment Report (similar to Phase 1)
2. **Continuous operation:** Leave daemon running with nightly audit cycles (cron)
3. **Frontier research:** Investigate adaptive learning (daemon reads audit verdicts and modifies behavior)
4. **Publication:** Engineering Studio v4 is production-ready, suitable for peer review

---

## Key Files

| Path | Purpose |
|---|---|
| `run_autonomous_phase2.sh` | Start the daemon with all systems live |
| `.observatory/evidence_ledger.sqlite3` | Immutable hash-chained event log |
| `.observatory/reports/` | Daily audit reports (JSON, timestamped) |
| `.daemon.log` | Daemon stderr/stdout |
| `systems/engineering_studio/studio_v4/` | All Phase 2 implementation (storage, executor, audit) |
| `systems/engineering_studio/studio_v3/observatory/` | Phase 1 Observatory (immutable, trusted) |

---

**Integration Test Status:** Ready to launch  
**Autonomous Operation:** All systems green  
**Next Checkpoint:** 24 hours (first audit cycle)
