# SENTINEL SIGNAL ENGINE AUDIT
**NEXUS Federation F5.1 — 2026-08-28**
**Subject:** `frontier_ingest.py :: signal_worker()` / `technicals_worker()`

## Inputs
- `intelligence_scores` (most recent row per symbol, by `generated_at`) —
  itself produced by `technicals_worker()` from `prices_daily` (120-row
  trailing window per symbol).

## Outputs
- `signals_unified` (`INSERT OR IGNORE`, `UNIQUE(ts, symbol, source)`).

## DB tables touched
- Read: `intelligence_scores`, `prices_daily`.
- Write: `intelligence_scores` (by `technicals_worker`), `signals_unified`
  (by `signal_worker`).
- No execution-adjacent table (`frontier_decisions`,
  `frontier_shadow_executions`, `frontier_portfolio_runs`,
  `frontier_execution_capacity`, `frontier_optimizer_runs`) is reachable
  from either function — confirmed by reading both functions in full;
  neither imports nor references any of those tables.

## Required freshness
`_frontier_price_freshness()`: FRESH ≤1 day, STALE 2–5 days, OLD >5 days,
UNKNOWN if unparseable. `technicals_worker` gates on this BEFORE computing
technicals — a stale/unknown latest price short-circuits to a `NO_SIGNAL`
row and returns, never computing RSI/SMA/etc. on stale data.

## Failure behavior
- Fewer than 20 price rows for a symbol → silent early return, no row
  written at all (not even NO_SIGNAL). Verified in code
  (`if len(rows) < 20: return`).
- Any exception inside `technicals_worker`/`signal_worker` is caught and
  logged at `debug` level (`except Exception as e: log.debug(...)`) —
  one symbol's failure never aborts the batch. This is a deliberate,
  reasonable choice for a 360-symbol batch job, though it means a
  systemic bug (like the one found and fixed in this mission) can persist
  silently for a long time without raising an alarm — nothing here alerts
  on an all-symbols-degraded condition specifically. Not fixed in this
  mission (out of the "restore, don't redesign" scope); worth a future
  observability addition.

## Idempotency
- `intelligence_scores`: `INSERT OR IGNORE` with `UNIQUE(symbol,
  generated_at)` (verified directly against the live schema) — a
  byte-identical re-run is impossible to duplicate unless it recomputes
  the exact same `generated_at` value, which `datetime.now().isoformat()`
  (microsecond resolution) makes practically impossible across two real
  invocations.
- `signals_unified`: `UNIQUE(ts, symbol, source)`, `INSERT OR IGNORE` —
  a genuine re-run against unchanged `intelligence_scores` is a true
  no-op (same `ts` copied straight from `intel['generated_at']`).

## Look-ahead protection
`technicals_worker` reads the 120 most recent `prices_daily` rows for a
symbol as of the moment it runs; nothing in either function reads a price
dated later than "now." No look-ahead risk found.

## Execution coupling
**None.** Neither function contains a write, an import, or a reference to
any execution-adjacent table or any broker/exchange client. Proven safe
to run repeatedly without any execution-authority implication — confirmed
directly in this mission's isolated test (execution_mode/execution_allowed
pairs identical before and after 360 `signal_worker` calls).

## Defect found and fixed during this audit

`technicals_worker`'s happy-path `INSERT INTO intelligence_scores` did not
include `latest_price_date`/`freshness`/`data_status` at all (NULL on
every successful, non-stale run), while `signal_worker` reads
`intel['freshness'] or "UNKNOWN"` — silently marking every genuinely fresh
signal as `UNKNOWN`, which the downstream `frontier_actionable_signals`
VIEW then always excluded. See F5.1 pipeline commit (Sentinel repo,
`56ec4e0`) for the fix and SENTINEL_FRESHNESS_RESTORATION_EVIDENCE.md for
the before/after proof.

## Test coverage

**None found.** No test file references `technicals_worker` or
`signal_worker` by name (`grep -r` across `tests/`). This audit is the
first documented verification of either function's behavior beyond the
original author's own manual testing. Recommended follow-up (not
performed in this mission): unit tests for the freshness gate and the
now-fixed happy-path column stamping, to prevent this exact class of
regression recurring silently.

## Verdict

**SAFE TO SCHEDULE.** No execution coupling, bounded failure mode, real
(if imperfect) idempotency, one real defect found and fixed.
