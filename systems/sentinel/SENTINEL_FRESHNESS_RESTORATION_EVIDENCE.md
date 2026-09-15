# SENTINEL FRESHNESS RESTORATION EVIDENCE
**NEXUS Federation F5.1 — 2026-08-28**

## Sequence executed (in order)

1. Baseline captured (SENTINEL_F5_1_BASELINE.md) before any change.
2. Price-date forensics (SENTINEL_PRICE_DATE_FORENSIC_REPORT.md) → 689
   malformed rows classified (687 DUPLICATE, 2 UNKNOWN).
3. Repair applied: `migrations/20260828_prices_daily_date_quality_repair.py`
   (Sentinel repo commit `d60fbff`) — 689 rows quarantined + removed,
   `trg_prices_daily_date_format` gate installed.
4. Signal/decision/regime engine audits (SENTINEL_SIGNAL_ENGINE_AUDIT.md,
   SENTINEL_DECISION_ENGINE_AUDIT.md, SENTINEL_REGIME_ENGINE_AUDIT.md) —
   all three classified SAFE_TO_SCHEDULE, no execution coupling found.
5. Isolated run against a throwaway copy of the (already-repaired) real
   database — full chain, monkeypatched DB_PATH, real production DB
   never touched.
6. Defect found during the isolated run: `technicals_worker`'s happy-path
   INSERT never stamped `latest_price_date`/`freshness`/`data_status`,
   so every genuinely fresh signal read back as `freshness=NULL→"UNKNOWN"`
   downstream — silently excluding it from `frontier_actionable_signals`
   regardless of true freshness. Fixed (Sentinel repo commit `56ec4e0`).
7. Isolated run repeated with the fix — full chain succeeded, 330 new
   decisions and 1 new regime row from genuinely current data.
8. Same fix wired into `frontier_pipeline.py`'s scheduled dispatch as
   three new stages (`signals`, `decisions`, `regime`) — same commit.
9. Live cycle run for real against production
   `financial_intelligence.db`, via the actual entrypoint
   (`python3 -m sentinel.frontier_pipeline --stage <x>`), one stage at a
   time: `technicals` → `signals` → `decisions` → `regime`.

## Live cycle evidence (step 9, production database)

| Metric | Before | After |
|---|---|---|
| `frontier_decisions` row count | 330 | 660 |
| `frontier_market_regime` row count | 1 | 2 |
| `signals_unified` row count | 60,564 | 60,924 |
| Latest signal `ts` | 2026-08-14T06:53:35 | **2026-08-28T05:54:46** |
| Latest decision `created_at` | 2026-08-14T00:03:27+00:00 | **2026-08-27T22:54:47+00:00** |
| Latest regime `generated_at` | 2026-08-14T00:15:04+00:00 | **2026-08-27T22:54:48+00:00** |
| `frontier_decisions` exec pairs | `[('SHADOW', 0)]` | `[('SHADOW', 0)]` — unchanged |
| `frontier_shadow_executions` exec pairs | `[('SHADOW', 0)]` | `[('SHADOW', 0)]` — unchanged |

## Sample new decision IDs (real, from the live run)

```
FD-d1733fc0a24b3442146a  VCB  WATCH       2026-08-27T22:54:47.486138+00:00
FD-c1e0a032a153add63e89  BID  NO_TRADE    2026-08-27T22:54:47.486130+00:00
FD-5453f92f2aafaa946210  CTG  WATCH       2026-08-27T22:54:47.486120+00:00
FD-00dfcd263c5c76e264da  TCB  SHADOW_BUY  2026-08-27T22:54:47.486113+00:00
FD-03b267bb3af98bbb815d  MBB  WATCH       2026-08-27T22:54:47.486105+00:00
```

## New regime row (real, from the live run)

```json
{
  "id": 2,
  "generated_at": "2026-08-27T22:54:48.112581+00:00",
  "market_date": "2026-08-27",
  "universe_size": 359,
  "usable_symbols": 359,
  "regime": "SIDEWAYS",
  "composite_regime_score": -13.074226010434472,
  "confidence": 0.3352610205998575,
  "exposure_multiplier": 0.75,
  "data_quality": "HIGH"
}
```

This is a fresh `MODEL_ESTIMATE`, not a historically validated signal —
see SENTINEL_REGIME_ENGINE_AUDIT.md's "Historical evaluation" section:
this regime classifier has never been backtested. Freshness is restored;
predictive accuracy was never established and is not claimed here.

## Execution safety — before/after, both isolated and live runs

Checked at every step (isolated test, scheduler-dispatch test, and the
real production run): `SELECT DISTINCT execution_mode, execution_allowed
FROM frontier_decisions` and the same query against
`frontier_shadow_executions` returned `[('SHADOW', 0)]` in every case,
before and after. **LIVE_EXECUTION_OCCURRED = FALSE** throughout.

## What remains stale (honestly, by design)

- `macro_indicators`: latest period `2023-01-01` — a quarterly/annual-
  cadence series, unaffected by this restoration and not expected to
  change from a daily-pipeline fix. Explicitly disclaimed in Sentinel's
  InstitutionalReport (`STALE_DATA` limitation), never presented as
  current.
- `historical_validation_executions` (walk-forward/backtest ledger):
  0 rows — `NOT_COMMISSIONED`, unrelated to this mission's scope.
- `forecasting`: no capability exists in the observed source at all
  (`NOT_COMMISSIONED`) — this mission restores analytical freshness, not
  predictive capability, and does not claim otherwise.
- VNStock rate limiting: `EXTERNAL_DEPENDENCY_DEGRADED`, unresolved (no
  tier purchased, no provider switched, per explicit mission constraint).
  The existing per-process throttle (`frontier_ingest.py::
  _vnstock_throttle`) mitigates but does not eliminate exhaustion.

## Report replay idempotency

See `systems/sentinel/tests/f5/test_f5_three_process_e2e.py::
test_f5_report_replay_receipt_vs_state_transition` for the executed
proof: replaying the identical `InstitutionalReport` through the kernel
grows `report_log` (a receipt-event audit trail — 2 rows → 3 rows) but
leaves `state_event_log` unchanged (15 rows → 15 rows), with the kernel's
own `temporal_classification` reporting `DUPLICATE` on the replay. This
is pre-existing kernel behavior (`kernel.py`'s DUPLICATE branch), verified
here specifically for Sentinel rather than newly built.
