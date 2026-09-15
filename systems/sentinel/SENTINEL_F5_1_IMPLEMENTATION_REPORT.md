# SENTINEL F5.1 IMPLEMENTATION REPORT
**NEXUS Federation F5.1 — 2026-08-28**
**Mission:** Decision/regime pipeline restoration, market-date data quality
repair, and final Sentinel freshness commissioning.

## What this mission restored

F5 (the prior mission) integrated Sentinel into the federation honestly,
including surfacing that `frontier_decisions`/`frontier_market_regime`
were 13 days stale. F5.1's job was to find out *why*, and fix it if the
fix was safe and in-scope — not to redesign Sentinel, not to add
execution, and not to let progress here wait on the (separately tracked,
still-unresolved) VNStock rate limit.

Two independent defects were found, both required for restoration, both
fixed:

1. **A data-quality defect** in `prices_daily`: 689 rows with a
   malformed `date` value (`'0'`–`'3'` instead of `YYYY-MM-DD`),
   traced to a fallback in `write_prices()`'s date-column heuristic.
   687/689 were confirmed exact-value duplicates of an already-correct
   row; 2 could not be matched. Quarantined (never fabricated),
   removed, and a schema-level gate installed against recurrence.
   → SENTINEL_PRICE_DATE_FORENSIC_REPORT.md,
   SENTINEL_DATA_QUALITY_GATE_SPEC.md

2. **An architectural gap**: the scheduled pipeline
   (`frontier_pipeline.py`, the actual daily cron entrypoint) never
   dispatched signal, decision, or regime generation — only
   discovery/prices/fundamentals/company/technicals. The mechanisms
   themselves (`signal_worker`, `decision.frontier_decision_engine`,
   `risk.frontier_regime_engine`) already existed and worked; they were
   simply never wired in after whatever migration replaced the older
   `frontier_ingest.run_full_pass()` entrypoint. A related, smaller
   defect (`technicals_worker`'s happy path never stamped freshness
   metadata) meant that even after scheduling the new stages, every
   genuinely fresh signal would still have been silently excluded from
   decision generation — found and fixed in the same change.
   → SENTINEL_DECISION_PIPELINE_FORENSIC_REPORT.md,
   SENTINEL_SIGNAL_ENGINE_AUDIT.md, SENTINEL_DECISION_ENGINE_AUDIT.md,
   SENTINEL_REGIME_ENGINE_AUDIT.md

Neither defect was execution-related. Both were verified safe in
isolation before touching the real database or the real scheduler.

## What was explicitly NOT done (in-scope exclusions, by design)

- **No VNStock tier purchased, no provider switched.** Rate limiting is
  tracked as `EXTERNAL_DEPENDENCY_DEGRADED`, separate from and no longer
  blocking analytical freshness (prices_daily was already current
  throughout this mission; the rate limit affects throughput, not the
  freshness this mission restores).
- **`shadow/frontier_shadow_engine.py::create_shadow_entries()`** — found
  during the decision-engine audit to read `frontier_decisions` but,
  like the stages this mission fixed, is not called by any scheduled
  entrypoint. Deliberately **not** wired in: it sits one step closer to
  execution simulation than analytical decision generation, and this
  mission's explicit boundary ("analysis pipeline ≠ execution pipeline")
  means it deserves its own dedicated audit, not a side-effect inclusion
  here.
- **No test authorship for the newly-scheduled engines.** All three
  (`signal_worker`, `build_decisions`, `calculate_regime`) had zero
  dedicated test coverage before this mission and still do — this
  mission verified their behavior directly (isolated run + live run,
  both with concrete evidence) but did not backfill unit tests, to keep
  the change scoped to restoration rather than expanding into new test
  authorship.
- **No CHECK constraints added beyond the one date-format gate** —
  evaluated all six bounded-quality-gate categories the mission
  suggested; only the date-format gate had actual defect evidence behind
  it (SENTINEL_DATA_QUALITY_GATE_SPEC.md's table).

## Commits

**Sentinel repo** (`completion/final-shadow-stages`):
- `d60fbff` — price-date repair migration + gate
- `56ec4e0` — signals/decisions/regime scheduler wiring + technicals
  freshness-stamp fix

**NEXUS repo** (`main`):
- Executor updated (`runtime/frontier_analysis_executor.py`) with
  explicit `signal_engine`/`decision_engine` freshness components,
  per-component (not global) freshness computation, and corrected
  recommendations/risks reflecting the now-resolved architectural gap.
- F5 test suite extended from 6 to 8 tests: the original negative
  control was repointed at `macro_data` (still genuinely stale) since
  `regime` is no longer a valid stale example after this mission's
  restoration; two new tests added for report-replay idempotency
  (section 20) and the NEXUS state-transition proof (section 18).
- Seven new documentation deliverables (this file plus the six named in
  the mission brief).

## An honest process note

While tracing decision-engine consumers, I found and initially wrote an
incorrect claim in this mission's own audit draft ("no consumer writes
based on frontier_decisions' content") before `grep` turned up
`create_shadow_entries()`. Caught before finalizing, corrected in
SENTINEL_DECISION_ENGINE_AUDIT.md rather than left standing. Recorded
here as the standard this mission held itself to: a wrong claim gets
corrected the moment it's found, not smoothed over.
