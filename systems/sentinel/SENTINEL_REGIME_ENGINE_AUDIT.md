# SENTINEL REGIME ENGINE AUDIT
**NEXUS Federation F5.1 — 2026-08-28**
**Subject:** `risk/frontier_regime_engine.py :: calculate_regime()`

## Input features
Per-symbol trailing 90-day OHLCV window from `prices_daily` (`market='VN'
OR market IS NULL`, `close IS NOT NULL AND close > 0`), requiring at
least `MIN_HISTORY = 65` rows to be usable. Aggregated across all usable
symbols into breadth (`% above SMA20/SMA60`), momentum
(`% positive 5d/20d`, median 5d/20d return), and volatility (20-day
annualized std of daily returns) statistics.

## Algorithm / model
Purely deterministic, hand-specified scoring — **not** a fitted or
trained model:
- `_score_breadth`, `_score_momentum`, `_score_trend`, `_score_volatility`:
  fixed linear/piecewise formulas over the aggregate statistics above.
- `composite_regime_score`: a weighted combination of the four component
  scores (weights stated directly in code, not learned).
- `_classify(score)`: a fixed threshold ladder (`≥55 STRONG_BULL`, `≥20
  BULL`, `>-20 SIDEWAYS`, `>-55 BEAR`, else `STRONG_BEAR`).

Report contract classification: **MODEL_ESTIMATE** for the composite
score/regime label (it is a model's output, carried through unchanged),
not `DERIVED_METRIC` (a `DERIVED_METRIC` is a plain arithmetic
transform like "days since X"; a regime classification is a modeling
judgment even though the model itself is simple and fully auditable) and
never `OBSERVED_MARKET_FACT`.

## Timestamp semantics
`generated_at` = wall-clock time the function ran. `market_date` = the
single most recent date in `prices_daily` (`MAX(date)`), i.e. the trading
day the regime characterizes — these are two different things and the
schema correctly keeps them as separate columns. **Defect found and
fixed as part of this mission** (not a new code change to this file,
but to its upstream data): `_latest_market_date()`'s `SELECT MAX(date)`
has no format filter and would have silently returned `'3'` as the
"latest market date" had it been run before the malformed-row repair
(SENTINEL_PRICE_DATE_FORENSIC_REPORT.md) — `'3'` sorts lexically after
any real `YYYY-MM-DD` string. No code change was made to this file
itself; the fix was at the data layer (repair + `trg_prices_daily_date_
format` gate), which resolves the defect for every reader of
`prices_daily`, this one included, without engine-specific patching.

## Confidence semantics
`confidence` is a separate field from `composite_regime_score`, computed
independently (reviewed in code but not reproduced formula-by-formula in
this audit — out of scope for a restoration mission; flagged as a
follow-up if regime confidence is ever used for a consequential decision).
Not derived from a formal statistical procedure (e.g. a fitted model's
predicted-probability output) — it is another hand-specified heuristic,
same epistemic category as the regime score itself.

## Historical evaluation
**None found.** No backtest, no walk-forward validation, no historical
accuracy record for this regime classifier exists anywhere in the
observed codebase or database (`historical_validation_*` tables are
scoped to the execution-engine's own next-session-entry backtests, not
to regime classification). The regime label this mission generated live
(`SIDEWAYS`, composite score −13.07, confidence 0.34) has **zero**
historical track record behind it — it is a fresh, unvalidated model
output, not an empirically-tested signal.

## Known limitations
- No historical evaluation (above) — this is the most significant
  limitation and the reason this mission's report explicitly classifies
  the regime output as `MODEL_ESTIMATE`, never presented as fact.
- `MIN_HISTORY = 65` trading days required per symbol — a newly-listed
  symbol with less history is silently excluded from `usable_symbols`
  (359 of 360 in this mission's live run — one symbol excluded, not
  investigated further as it does not affect correctness).
- Single-market assumption (`market='VN' OR market IS NULL`) — this
  engine has no multi-market regime concept; not a defect for Sentinel's
  current VN-only scope, but worth noting if the universe ever expands.

## DB tables touched
- Read: `prices_daily` only.
- Write: `frontier_market_regime` only. This table has **no**
  `execution_mode`/`execution_allowed` columns at all (confirmed against
  the live schema) — there is no execution-adjacent field to even
  misuse here; the entire table is descriptive/analytical by
  construction.

## Test coverage
**None found** (`find tests -iname "*regime*"` returns nothing). Same
gap as the decision engine.

## Verdict
**SAFE TO SCHEDULE.** No execution coupling (the table itself has no
execution field to couple to), deterministic and fully auditable
scoring, but genuinely unvalidated as a predictive signal — this
mission restores its *freshness*, not its *accuracy*, and the two must
not be conflated in Sentinel's report language (per mission section 22:
"Do not infer forecasting performance or profitability from freshness
repair").
