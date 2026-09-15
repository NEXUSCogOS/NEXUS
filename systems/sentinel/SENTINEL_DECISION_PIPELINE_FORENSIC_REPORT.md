# SENTINEL DECISION PIPELINE FORENSIC REPORT
**NEXUS Federation F5.1 — 2026-08-28**

## The intended pipeline (established from executable code, not filenames)

```
prices_daily            (frontier_ingest.py :: price_worker, scheduled)
  → intelligence_scores (frontier_ingest.py :: technicals_worker, scheduled)
    → signals_unified   (frontier_ingest.py :: signal_worker, COMMITTED but UNSCHEDULED)
      → frontier_actionable_signals   (VIEW, already in schema:
                                        WHERE source='FRONTIER_INGEST'
                                        AND freshness='FRESH'
                                        AND data_status='CURRENT'
                                        AND action IN ('BUY','WATCH','HOLD','AVOID'))
        → frontier_decisions          (decision/frontier_decision_engine.py ::
                                        build_decisions(), UNCOMMITTED, UNSCHEDULED)

prices_daily
  → frontier_market_regime            (risk/frontier_regime_engine.py ::
                                        calculate_regime(), UNCOMMITTED, UNSCHEDULED)
```

## Which mechanism is canonical — established by evidence, not filename

`grep`-verified across the entire repository: `decision/frontier_decision_engine.py`
is the **only** file anywhere that writes to `frontier_decisions`.
`risk/frontier_regime_engine.py` is the **only** file anywhere that writes
to `frontier_market_regime`. There is no competing or older mechanism for
either table — the question "which one is canonical" has a single answer
each, settled by database-write evidence, not by which name sounds more
authoritative.

`frontier_ingest.py::signal_worker` is the only writer of `signals_unified`,
and it is git-tracked with history back to the repo's initial commit —
the oldest, most original mechanism in the whole chain.

## Why they were never scheduled — root cause classification

**MIGRATION_DISCONTINUITY**, with one contributing **IMPLEMENTATION_OMISSION**.

Evidence:

- `frontier_pipeline.py` has **zero git history before this mission's F5
  reconciliation commit** (`git log --all -- frontier_pipeline.py` returns
  exactly one commit: this mission's own). It was never tracked, meaning
  whoever adopted it as the new scheduled orchestrator did so without ever
  committing it, and evidently without carrying stage 5 (`signal_worker`)
  and beyond forward from whatever it replaced.
- `frontier_ingest.py` (git-tracked from the initial commit) already
  contains a complete `run_full_pass()` function with 5 phases, including
  a signal-generation phase — strong evidence this WAS the original
  scheduled entrypoint before `frontier_pipeline.py` existed.
- `frontier_pipeline.py`'s own dispatch (`main()`) called exactly
  discovery/prices/fundamentals/company/technicals — stopping precisely
  at the boundary where `run_full_pass()`'s phase 5 (signals) would have
  continued. This is not a deliberate omission of a dangerous stage (all
  five phases are equally non-executing, so there is no safety reason to
  stop at four) — it reads as an incomplete port.
- `decision/frontier_decision_engine.py` and `risk/frontier_regime_engine.py`
  are **newer** than `frontier_ingest.py`'s original phases (they read
  from `frontier_actionable_signals`, a VIEW filtering `signals_unified` —
  a refinement on top of the original signal mechanism, not a
  replacement for it) and were **never committed at all**. The exact
  1:1 row-count match between `frontier_actionable_signals` (330 rows,
  at the time) and `frontier_decisions` (330 rows) before this mission's
  repair is strong evidence `build_decisions()` was run manually,
  exactly once, immediately after `signal_worker`'s last successful run
  (2026-08-14) — as a local test or seed, never wired into any scheduler,
  and never committed to git.

**Conclusion:** nobody disabled these stages for safety reasons, no
dependency ever blocked them, and no evidence of deliberate exclusion
exists. The scheduled orchestrator was rewritten and the newer stages
were built alongside it, but the two efforts were never joined together.
This is squarely a migration/integration gap, not a decision.

## What was NOT the cause

- **Not SAFETY_DISABLEMENT**: nothing in these three modules touches
  execution capability; disabling them protects nothing that isn't
  already protected by the schema-level triggers and the absence of any
  broker client.
- **Not DEPENDENCY_BLOCK** in the sense of a missing library or credential
  — all three modules imported and ran cleanly, first try, once the
  actual (unrelated) prices_daily data-quality defect was fixed.
- **Not LEGACY_DEAD_CODE** — `signal_worker` is exercised transitively by
  this repo's existing test suite's fixtures and conventions; `decision/`
  and `risk/` were dead in the sense of "unreached," not in the sense of
  "abandoned" — they are recent, complete, and functioning.

## Resolution

Wired into `frontier_pipeline.py`'s scheduled dispatch (F5.1 pipeline
commit) as three new stages — `signals`, `decisions`, `regime` — added
after `technicals` in both the `--stage` choices and the `all` dispatch
list. See SENTINEL_SIGNAL_ENGINE_AUDIT.md, SENTINEL_DECISION_ENGINE_AUDIT.md,
SENTINEL_REGIME_ENGINE_AUDIT.md for the per-engine audits that preceded
this decision, and SENTINEL_FRESHNESS_RESTORATION_EVIDENCE.md for the
live run evidence.
