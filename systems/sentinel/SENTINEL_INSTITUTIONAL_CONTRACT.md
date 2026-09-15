# SENTINEL INSTITUTIONAL CONTRACT
**NEXUS Federation F5 — 2026-08-28**

> **F5 PHASE 4 CORRECTIONS (2026-08-28, same day, later in the mission)**
> This document was written during Phase 3, before the Phase 4 runtime
> reconciliation and live three-process test. Two corrections, superseding
> specific claims below rather than silently rewriting them:
>
> 1. **"SQLite TRIGGER enforces shadow-only mode" / "BLOCKED" is
>    re-verified, but re-stated as `LIVE_EXECUTION_BLOCKED_BY_OBSERVED_
>    CONTROLS`, never "impossible" or "structurally unreachable".** Phase 4
>    directly queried `sqlite_master` and confirmed real `BEFORE INSERT`/
>    `UPDATE` triggers exist on all five execution-adjacent tables
>    (`frontier_decisions`, `frontier_shadow_executions`,
>    `frontier_portfolio_runs`, `frontier_execution_capacity`,
>    `frontier_optimizer_runs`), each raising `ABORT` if
>    `execution_mode != 'SHADOW'` or `execution_allowed != 0`, and that
>    every row ever written to `frontier_decisions` has recorded
>    `('SHADOW', 0)` -- no exception. No broker/exchange API client exists
>    anywhere in the observed source (grep-verified). These are real,
>    specific, verified controls -- but a SQLite trigger only gates writes
>    to that table; it cannot gate a hypothetical future code path that
>    calls a broker API directly without touching this table. See
>    SENTINEL_F5_PHASE_2A_REPORT.md and
>    `systems/sentinel/tests/f5/test_f5_three_process_e2e.py::
>    test_f5_live_execution_rejected` for the live-tested evidence.
>
> 2. **"14 days stale" was imprecise and is now corrected.** `prices_daily`
>    (raw market data) is CURRENT (latest verified: 2026-08-27, confirmed
>    once a date-format data-quality defect in that table was filtered
>    out -- see `runtime/frontier_analysis_executor.py`). Only
>    `frontier_decisions`/`frontier_market_regime`/`signals_unified` are
>    stale (13 days as of this correction), and NOT solely because of the
>    VNStock rate limit: `frontier_pipeline.py`'s scheduled entrypoint
>    never calls the signal/decision-generation stage at all
>    (architectural gap, verified by direct code inspection). Resolving
>    the rate limit alone would not restore decision freshness. See the
>    ARCHITECTURAL_GAP finding in `runtime/frontier_analysis_executor.py`
>    and the F5 Phase 4 final report for full detail.

## Sentinel-specific federation integration

Sentinel does NOT own a bespoke institutional contract module. Instead, mission reports are built directly against NEXUS Federation's institution-agnostic contract:
`nexus_federation/contracts/generic.py`.

This allows Sentinel to integrate as a third specialist institution alongside Librarian and DAT.AI, each contributing to federation-wide capabilities without duplicating validation logic.

## Registration

```python
# ingress/contract_registry.py
"sentinel": ContractRegistration(
    validate_fn=validate_generic_report,
    known_schema_versions=frozenset({"1.0.0"}),
)
```

Adding Sentinel requires ONE registry entry — zero changes to core federation logic.

---

## Institutional Mission

**Domain:** Financial Intelligence & Market Execution Simulation

**Role in Federation:**
- Provides market data ingestion, portfolio tracking, and decision simulation
- Reports on financial state, execution readiness, and market regime detection
- Specializes in Vietnamese market data and multi-asset portfolio optimization
- Operates entirely in SHADOW (simulation) mode with zero live execution

---

## Real Capability Statuses

Based on Phase 2A audit (SENTINEL_F5_PHASE_2A_REPORT.md):

| Capability | Lifecycle | Basis | Evidence |
|---|---|---|---|
| `market_data_ingestion` | DEGRADED | VNStock rate-limited but provider functional | Last successful ingest: 2026-08-14 |
| `portfolio_tracking` | INTEGRATED | 58 schema tables, 170MB healthy database | PRAGMA quick_check: ok |
| `execution_simulation` | INTEGRATED | Shadow mode enforced via SQLite TRIGGER | execute_trades() blocked |
| `frontier_regime_detection` | INTEGRATED | frontier_market_regime table populated | 1 record present |
| `decision_synthesis` | INTEGRATED | frontier_decisions table active | 330 records (2026-08-14) |
| `executive_delegation_receiver` | NOT_COMMISSIONED | Code present but untested in federation context | To be verified in Phase 5 test |
| `risk_attribution` | INTEGRATED | risk tables present in schema | Historical data available |

### Operating State Derivation

Sentinel's `operating_state` is derived (never self-asserted) from its primary capability (`market_data_ingestion`)'s lifecycle:

**Current:** `DEGRADED`
- **Reason:** VNStock API rate-limited (60 requests/minute community tier exhausted)
- **Impact:** Data freshness stale (14 days without update)
- **Recovery:** Reversible — upgrade API tier or implement exponential backoff
- **Safety:** No code defect; schema integrity intact

**Requirements for `INTEGRATED`:**
1. Fix rate-limit issue (upgrade plan or backoff logic implemented)
2. Successful ingest cycle within last 7 days
3. Data freshness within operational bounds

**Requirements for `OPERATIONAL`:**
- `INTEGRATED` + external attestation (federation kernel certification after test)

Per federation discipline, Sentinel structurally cannot self-promote — only federation kernel can set `OPERATIONAL` after successful delegation cycle.

---

## Typical Outputs (Real vs. Not Yet)

| Output | Status | Notes |
|---|---|---|
| Market data snapshots | ✅ REAL | VNStock ingestion (rate-limited) |
| Portfolio state | ✅ REAL | Tracked in financial_intelligence.db |
| Execution decisions | ✅ REAL | frontier_decisions table, 330 records |
| Shadow execution results | ✅ REAL | Simulated via historical/execution_engine.py |
| Live execution | ❌ BLOCKED | SQLite TRIGGER enforces shadow-only mode |
| Risk analysis | ✅ REAL | Risk tables present, analysis available |
| Market regime detection | ✅ REAL | frontier_market_regime identified |
| Hypothesis generation | ❌ NOT_COMMISSIONED | Code exists but untested |
| Backtesting engine | ⚠️ PARTIAL | Infrastructure present, last successful run: 2026-08-14 |
| Cross-system implications | ⚠️ FIELD_EXISTS | Populated only if real federation-wide implication found |

---

## Data Authority

**Primary Data Store:**
- `${NEXUS_ROOT}/systems/sentinel/financial_intelligence.db`
- Size: 170 MB
- Status: HEALTHY (PRAGMA quick_check: ok)
- Journal Mode: WAL (Write-Ahead Logging)
- Schema Version: 1

**Data Freshness:**
- Last successful ingest: 2026-08-14 (14 days old)
- Current status: STALE
- Cause: Provider rate-limit (VNStock)
- Safe for testing: YES (with caveat: data is historical)

**Execution Safety Gates (Schema-level):**
```sql
-- All execution decisions enforce these constraints:
execution_allowed DEFAULT 0    -- binary gate
execution_mode DEFAULT 'SHADOW' -- only shadow allowed
-- TRIGGER blocks any attempt to set execution_allowed ≠ 0 or execution_mode ≠ 'SHADOW'
```

No code can bypass these; they're enforced at SQLite layer before Python ever sees the data.

---

## Code Authority

**Runtime Code:**
- `${HOME}/sentinel/` (uncommitted branch: `completion/final-shadow-stages`)
- 7 modified files (all active runtime improvements)
- Status: Production code running from working tree

**Phase 2A Findings:**
- ✅ Deployed code = Working Tree (all improvements active)
- ⚠️ Working Tree ≠ Git HEAD (must commit formally)
- ✅ No execution defects found
- ✅ Concurrency controls present (locking added)

**Required Before Federation Integration:**
1. Commit 7 active runtime changes
2. Update package version in setup.py
3. Create formal release tag

---

## Configuration Authority

**Configuration Source:**
- `${HOME}/sentinel/config/.env` (secrets not inspected)
- Sourced by: `bin/run_ingest.sh`
- Credentials: VNStock API keys, TCBS auth, Vnai client
- Status: PRESENT and LOADED

---

## Scheduler Authority

**LaunchAgent Jobs:**
```
com.sentinel.ingest          (LOADED, exit code 1 — rate-limited)
com.sentinel.shadow-cycle    (LOADED)
com.sentinel.monitor         (LOADED)
com.sentinel.backtest        (LOADED)
com.sentinel.frontier-stage  (LOADED)
com.sentinel.frontier-deploy (LOADED)
```

**Schedule:**
- Ingest: Every 15 minutes (900s)
- Status: Running but failing (rate-limit)
- Cron monitor: Hourly

---

## Provider Status Matrix

| Provider | Service | Domain | Status | Issue |
|---|---|---|---|---|
| **VNStock** | Market prices | Vietnamese stocks | RATE_LIMITED | 60 req/min exhausted |
| **TCBS** | News/fundamentals | Vietnamese | FAILING | Consistent failures (TBD) |
| **Vnai** | AI-augmented data | Vietnamese | AVAILABLE | Status present in logs |

**Overall Provider Health:** DEGRADED

---

## Execution Surface Audit

**All Reachable Execution Paths:**

1. `frontier_decision()` 
   - Produces: Decisions with `execution_allowed=0`
   - Gate: Schema DEFAULT

2. `frontier_pipeline()`
   - Routes: Signals → Decisions → Shadow Execution
   - Gate: Schema TRIGGER

3. `execute_trades()`
   - Blocked: SQLite prevents `execution_allowed≠0`
   - Gate: Schema-level enforcement

**Verdict:** ✅ NO LIVE EXECUTION REACHABLE

All paths terminate in shadow (simulation) mode. No code can invoke live trades regardless of logic flow.

---

## Known Issues & Mitigation

### Issue 1: Data Staleness (Active)
- **Status:** Last update 2026-08-14 (14 days old)
- **Cause:** VNStock rate-limited
- **Impact:** F5 tests will use historical data
- **Mitigation:** Document caveat in test results; fix rate-limit before production use

### Issue 2: TCBS Provider Failures (Active)
- **Status:** Failing per logs, root cause TBD
- **Impact:** Missing secondary data source
- **Mitigation:** Investigate TCBS API status post-commission

### Issue 3: Uncommitted Code in Production (Medium)
- **Status:** 7 files modified, not committed
- **Impact:** Deployment state unclear
- **Mitigation:** Commit formal release before federation integration

### Issue 4: Rate-Limit Not Addressed (Medium)
- **Status:** No backoff logic or upgrade plan
- **Impact:** Next ingestion will also fail
- **Mitigation:** Implement exponential backoff or upgrade API tier

---

## Federation Integration Status

**Phase 2A Complete:** ✅
- Root-cause analysis: COMPLETE
- Database integrity: VERIFIED
- Execution safety: VERIFIED
- Code authority: CLASSIFIED

**Ready for Phase 3:** ✅ YES
- Can create institutional report from current state
- Can register Sentinel in federation
- Can design F5 delegation test
- Can verify execution_allowed gate via test

**Phase 3 Objectives:**
1. Register Sentinel in federation contract registry
2. Create SENTINEL_INSTITUTIONAL_REPORT.md
3. Document capabilities and limitations
4. Design Phase 5 delegation test (market regime detection)

**Phase 4 Objectives:**
1. Integrate Sentinel as third institution in federation
2. Test three-process pipeline (NEXUS → Sentinel → NEXUS)
3. Verify crash recovery and idempotency
4. Prove Sentinel can accept delegated research missions

---

## Test Plan (Phase 5)

**Delegation Mission:** Market regime detection in Vietnamese equities

**Research Question:** "What market regime signals does the frontier decision engine detect in VN stock data from 2026-08-14?"

**Expected Outputs:**
- Regime classification (bull/bear/consolidation)
- Supporting decision table entries
- Execution readiness assessment
- Risk/opportunity matrix

**Safety Verification:**
- ✅ Verify execution_allowed gate blocks live trades
- ✅ Verify all shadow execution only
- ✅ Verify federation kernel accepts report
- ✅ Verify crash recovery (simulated Process C failure)

---

## Conclusion

Sentinel is a **financial intelligence specialist institution** integrated into NEXUS Federation. It provides:

- ✅ Market data collection (degraded due to rate-limit, recoverable)
- ✅ Portfolio tracking (healthy, 170MB database verified)
- ✅ Execution simulation (shadow-only, schema-enforced)
- ✅ Decision synthesis (frontier regime detection proven)

**Status:** READY FOR FEDERATION INTEGRATION

**Data Status:** STALE but SAFE (14 days old, suitable for testing with caveat)

**Safety Certification:** ✅ NO LIVE EXECUTION REACHABLE (schema enforces shadow-only)

**Next Step:** Proceed to Phase 3 institutional report generation.

---

**Contract Date:** 2026-08-28  
**Authority:** NEXUS Federation (F5 Sentinel Recovery Mission)  
**Certification:** Institutional integration approved pending formal code commit
