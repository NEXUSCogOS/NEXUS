# SENTINEL DECISION ENGINE AUDIT
**NEXUS Federation F5.1 — 2026-08-28**
**Subject:** `decision/frontier_decision_engine.py :: build_decisions()`

## Inputs
`frontier_actionable_signals` (a VIEW: `SELECT * FROM signals_unified
WHERE source='FRONTIER_INGEST' AND freshness='FRESH' AND
data_status='CURRENT' AND action IN ('BUY','WATCH','HOLD','AVOID')`) —
filtered at read time to the same universe `signal_worker` already
gates for freshness. No direct read of `prices_daily` or
`intelligence_scores`.

## Derived metrics
- `decision_score = round(score * confidence, 2)` — a simple product of
  the upstream signal's own score and confidence, not a new model.
- `position_weight`: a deterministic linear function of `score` and
  `confidence`, capped at `MAX_WEIGHT = 0.05` (5%). Zero for any action
  other than the internal `SHADOW_BUY` reclassification.
- `risk_level`: a fixed lookup table keyed on `(action, score)`.

None of these are machine-learned or fit to historical outcomes — all
are fixed, auditable arithmetic rules stated directly in the function
body. Classification for the report contract: `DERIVED_METRIC`, not
`MODEL_ESTIMATE`.

## Signal dependency
Direct, single dependency on `frontier_actionable_signals` — no fallback,
no secondary source. If `signals_unified` stops updating (as it did for
13 days, per this mission's own findings), `build_decisions()` degrades
silently to `signals_seen=0` or to re-processing the same stale signals
forever (see "Idempotency" below) — it does not raise, warn, or flag
staleness itself. Freshness enforcement lives entirely upstream, in
`signal_worker`/`technicals_worker`.

## Regime dependency
**None.** `build_decisions()` never reads `frontier_market_regime`. The
decision and regime engines are independent, parallel consumers of the
same upstream data (signals for one, prices for the other), not a
pipeline where one feeds the other. This was assumed producible in
either order; testing confirmed both orders work (this mission ran
`decisions` before `regime` in production).

## Portfolio inputs
None. No read of any `frontier_portfolio_*` table.

## Output table
`frontier_decisions`. Columns include `execution_mode`, `execution_allowed`
— both hardcoded literal `'SHADOW'` / `0` in the `INSERT` statement
itself (not merely relying on the column `DEFAULT`), on top of the
database's own `trg_decision_shadow_only` trigger (`BEFORE INSERT ...
WHEN execution_mode <> 'SHADOW' OR execution_allowed <> 0 THEN
RAISE(ABORT)`) — two independent layers, code and schema, both agreeing.

## `execution_allowed` behavior — GENERATE_DECISION vs EXECUTE_DECISION

`build_decisions()` implements **GENERATE_DECISION only**. It writes a
row describing what a shadow position *would* look like
(`decision_action`, `position_weight`, `risk_level`) and nothing more —
no code path in this file, or reachable from it, ever reads
`execution_allowed` to decide whether to *act*. Searched the entire
Sentinel source tree for any consumer of `frontier_decisions.decision_id`
that could constitute an EXECUTE_DECISION step: the only consumers found
are `observability/sentinel_status.py` (read-only reporting) and this
mission's own `frontier_analysis_executor.py` (read-only). **No
EXECUTE_DECISION mechanism exists anywhere in the observed codebase.**
This is the same finding as the F5 Phase 4 audit's execution-surface
map, re-confirmed here specifically for the newly-scheduled decision
engine.

## Shadow mode handling
Absolute — every row this function can produce carries
`execution_mode='SHADOW', execution_allowed=0`. There is no code path,
parameter, or configuration flag in `build_decisions()` that can produce
any other value. Verified by reading the entire function (73 lines) —
no conditional branch touches these two fields.

## Downstream consumers
- `observability/sentinel_status.py` (reporting only)
- This mission's `runtime/frontier_analysis_executor.py` (read-only,
  NEXUS federation reporting)
- **`shadow/frontier_shadow_engine.py::create_shadow_entries()`** DOES
  read `FROM frontier_decisions` to construct `frontier_shadow_executions`
  rows (still shadow-only: it too writes `execution_mode='SHADOW',
  execution_allowed=0`, and `frontier_shadow_executions` carries its own
  independent `trg_shadow_insert_live_block` trigger). Found while tracing
  consumers for this audit. **Not called by any scheduled process** —
  the live `bin/frontier-shadow-cycle` (F5-reconciled) only calls
  `measure_outcomes()`; its own comment says shadow-entry creation is
  "already integrated into the scheduled frontier runs, not here," but
  no scheduled entrypoint (`frontier_pipeline.py` before or after this
  mission's changes) calls `create_shadow_entries()` either. This is a
  second, adjacent migration-discontinuity gap, structurally identical
  in shape to the one this mission fixed for signals/decisions/regime —
  but it sits one step closer to execution simulation than analytical
  decision generation, so it is deliberately **not** wired in as part of
  this mission (out of F5.1's explicit scope: "analysis pipeline ≠
  execution pipeline," and shadow-execution creation warrants its own
  dedicated audit before being scheduled, not a side-effect inclusion
  here). Flagged as a candidate follow-up mission, not fixed.
- No other consumer found that writes to any table based on
  `frontier_decisions`' content.

## Idempotency
`decision_id = sha256(symbol|signal_ts|action)[:20]`, `INSERT` (not
`OR IGNORE`) wrapped in `try/except sqlite3.IntegrityError: skipped += 1`.
`decision_id` has `UNIQUE NOT NULL` on the `frontier_decisions` table
(verified against the live schema). A re-run against unchanged upstream
signals produces `inserted=0, skipped_existing=N` — proven directly in
this mission's isolated and live runs (`{'signals_seen': 330, 'inserted':
0, 'skipped_existing': 330}` on the second decisions-stage invocation
against the same signal set).

## Test coverage
**None found** (`find tests -iname "*decision*"` returns nothing). This
audit and the isolated/live runs performed during this mission are the
first documented verification of this function's behavior.

## Verdict
**SAFE TO SCHEDULE.** GENERATE_DECISION only, no EXECUTE_DECISION path
exists anywhere in the codebase, execution fields hardcoded plus
schema-trigger-enforced, idempotent by a real UNIQUE constraint. Missing
test coverage is a real gap, not fixed here (out of restoration scope).
