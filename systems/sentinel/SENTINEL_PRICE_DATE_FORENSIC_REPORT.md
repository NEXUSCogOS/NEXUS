# SENTINEL PRICE-DATE FORENSIC REPORT
**NEXUS Federation F5.1 — 2026-08-28**

## Summary

689 rows in `prices_daily` have a malformed `date` value (`'0'`, `'1'`, `'2'`, or `'3'` — a single ASCII digit instead of `YYYY-MM-DD`). All 689 are confirmed extraneous: **687 are exact-value duplicates of an already-correctly-dated row for the same symbol; 2 have no matching valid row and their true date cannot be recovered.**

## Quantification

| Malformed date value | Row count |
|---|---|
| `'0'` | 26 |
| `'1'` | 2 |
| `'2'` | 331 |
| `'3'` | 330 |
| **Total** | **689** |

All 689 rows: `source = 'VNStock'` exclusively (zero from Yahoo, the fallback provider).

## ID clustering — one contiguous ingestion run

```
date='3': id range 988882–989237 (330 rows)
date='2': id range 989216–989570 (331 rows)   -- overlaps the '3' range
date='1': id range 989238–989546 (2 rows)
date='0': id range 988937–989565 (26 rows)    -- overlaps '2' and '1'
```

The four malformed values are not four separate incidents — they are one
contiguous autoincrement-ID range (988882–989570, immediately following the
last known-good 2026-08-14 ingestion rows) in which the erroneous "date"
value drifts from `'3'` down through `'2'`/`'1'` to `'0'` as the batch
progresses. This is the signature of a small integer counter (range
0–3) being written into the date column partway through a single
per-symbol iteration loop — not four unrelated corruption events.

## Root-cause hypothesis (code-evidenced, not directly reproduced)

`frontier_ingest.py::write_prices()`:

```python
date_col = next((c for c in ['time', 'date', 'Date', 'index'] if c in df.columns), None)
...
date_val = str(row[date_col])[:10] if date_col else datetime.now().strftime('%Y-%m-%d')
```

The fallback chain's last candidate, `'index'`, is the column name pandas
assigns when `.reset_index()` is called on a DataFrame that does not carry
a genuine date-named column (e.g. a plain `RangeIndex`). If VNStock
returned a small, malformed, or truncated frame for a batch of symbols
under degraded/rate-limited conditions — one lacking `time`/`date`/`Date`
but incidentally exposing a bare positional `index` column — this fallback
would silently accept that positional integer (`0, 1, 2, 3, ...`) as the
"date," truncate it to `str(...)[:10]` (a no-op on a 1-digit string), and
insert it. This matches the observed values exactly (small integers,
`source='VNStock'` only, one contiguous ingestion batch).

**Confidence:** MODERATE-HIGH. This is the only fallback path in the
observed code capable of producing exactly this failure shape. It was not
independently reproduced against a live degraded VNStock response (doing
so would consume further rate-limited request budget without adding
material certainty, and is not required to classify or repair the
existing rows).

## Recoverability classification (per-row, all 689 rows checked)

| Classification | Count | Basis |
|---|---|---|
| **DUPLICATE** | 687 | Exact match (open, high, low, close, volume) against an existing valid-dated row for the same symbol. The correct data is already safely stored under its real date; these rows contribute no unique information. |
| **UNKNOWN** | 2 | Both `VC3` (dates `'3'` and `'2'`). VC3 has 1,270 valid-dated rows spanning 2021–2026-08-27, but no valid row has this exact OHLCV combination (25.1/25.1/24.5/24.8/636900). True date not recoverable from evidence available. |
| **RECOVERABLE** (date reconstructable but not equal to an existing row) | 0 | none found |
| **INVALID** (garbage OHLCV, not just garbage date) | 0 | none found — all 689 rows have plausible, non-null, non-zero OHLCV values |

Example (SHB, id 988882, date='3'): open=12.0 high=12.1 low=11.85
close=12.05 volume=50182500 — byte-identical to the valid row
`SHB / 2026-08-26` already in the table.

## Verified NOT a source of missing data

Every symbol with a malformed row also has a full, contiguous valid-dated
history reaching 2026-08-27 (e.g. `AAA`: 1,270 valid rows plus one `'2'`
and one `'3'` row). The malformed rows are pure duplicates layered on top
of intact data — removing them loses nothing.

## Consumption check — are these rows read by signal/decision/regime code?

**Yes, and dangerously.** `risk/frontier_regime_engine.py::_latest_market_date()`
runs `SELECT MAX(date) FROM prices_daily` with no format filter. Since `'3' >
'2026-08-27'` lexically, this call currently returns `'3'` as the
"latest market date" if run today — silently corrupting every downstream
regime calculation. This was independently confirmed live in Sentinel's own
production logs (`logs/frontier_pipeline_error.log`, 2026-08-27):
hundreds of `[TECH] <SYMBOL> NO_SIGNAL — UNKNOWN latest=3 age=None` lines,
where the technicals stage's own freshness gate is correctly refusing to
treat these rows as fresh (the gate working as designed) — but the
underlying rows remain, silently available to any query that isn't as
careful.

## Repair action taken

Per mission section 10 (repair where deterministically reconstructable;
quarantine, never fabricate, otherwise):

1. All 689 rows backed up verbatim, in full, to a new table
   `prices_daily_quarantine_20260828` (same columns + `quarantine_reason`,
   `quarantined_at`, `sha256_of_row`) — see
   SENTINEL_FRESHNESS_RESTORATION_EVIDENCE.md for the exact row count and
   hash manifest.
2. All 689 rows removed from `prices_daily` inside one transaction.
3. **No date was rewritten or fabricated for any row**, including the 687
   confirmed duplicates — they are removed (their correct data already
   exists under the real date), not "corrected in place," because
   rewriting `date='3'` to `date='2026-08-26'` for the SHB row above would
   violate `UNIQUE(symbol, date)` against the row that already legitimately
   holds that date.
4. A schema-level data quality gate (`trg_prices_daily_date_format`, see
   SENTINEL_DATA_QUALITY_GATE_SPEC.md) now silently rejects any future
   insert whose `date` is not `YYYY-MM-DD`-shaped, via `RAISE(IGNORE)` —
   consistent with the `INSERT OR IGNORE` pattern every writer already
   uses, so no application code required a change.
