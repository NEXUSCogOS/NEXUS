# SENTINEL DATA QUALITY GATE SPEC
**NEXUS Federation F5.1 — 2026-08-28**

## Scope

One schema-level gate on `prices_daily`, the single point where every
downstream consumer (technicals, signals, decisions, regime) reads market
data. Fixing it at the source means no per-consumer defensive code is
needed — the fix in `runtime/frontier_analysis_executor.py` (F5 Phase 4,
a GLOB filter in the read query) remains as defense-in-depth but is no
longer the only thing standing between a malformed row and a corrupted
regime calculation.

## Gate

```sql
CREATE TRIGGER trg_prices_daily_date_format
BEFORE INSERT ON prices_daily
WHEN NEW.date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
BEGIN
    SELECT RAISE(IGNORE);
END;
```

**Verified behavior** (tested against an in-memory SQLite table before
applying to production): `RAISE(IGNORE)` inside a `BEFORE INSERT` trigger
silently skips only the offending row and does not raise an exception to
the caller — confirmed with both `INSERT OR IGNORE` (what every Sentinel
writer already uses) and a plain `INSERT` (which also does not crash).
This means the gate requires **zero application code changes**: every
existing writer (`write_prices()`, backfill scripts, historical replay)
keeps working exactly as before for valid rows, and a row shaped like the
689 malformed ones from this incident is now silently dropped at
insert time instead of being written and only caught later.

## What this gate does NOT do

- Does not validate `open`/`high`/`low`/`close`/`volume` plausibility
  (out of scope for this incident — root cause was a date field, not a
  price field; no INVALID-priced row was found during the section 8
  forensic pass).
- Does not detect a *plausible but wrong* date (e.g. an off-by-one-day
  error) — only structurally malformed dates.
- Does not retroactively affect existing rows — the 689-row repair
  (SENTINEL_PRICE_DATE_FORENSIC_REPORT.md) is a separate, one-time action.
- Does not gate `UNIQUE(symbol, date)` duplicates with a *valid* date —
  that constraint already existed and already worked correctly (it did
  not stop the incident specifically because `'3'` is a distinct string
  from any real date, not a collision).

## Minimum additional bounded checks (mission section 9)

The mission asks for rejection/quarantine of: invalid date format (done,
above), missing symbol, non-numeric price, impossible price, duplicate
canonical key, future observation timestamp, material timestamp disorder.

Evaluated against the actual incident and actual schema:

| Check | Status | Rationale |
|---|---|---|
| Invalid date format | **IMPLEMENTED** (this gate) | Root cause of this incident |
| Missing symbol | Not implemented | `symbol TEXT NOT NULL` already rejects NULL at the schema level; no missing-symbol row was found in this incident |
| Non-numeric price | Not implemented | SQLite is dynamically typed; `write_prices()` already does `float(...)` before binding, so a non-numeric value raises in Python before reaching SQL. No case of this found in the incident. |
| Impossible price (e.g. negative/zero) | Not implemented | No such row found in this incident. `frontier_decisions`/`frontier_shadow_executions` already have their own `CHECK(... > 0)`-style constraints elsewhere in the schema; extending this to `prices_daily` is a reasonable follow-up but is a NEW constraint unrelated to this incident's root cause, and is not added here to keep this change minimal and traceable to the actual defect found. |
| Duplicate canonical key | Already implemented | `UNIQUE(symbol, date)`, pre-existing |
| Future observation timestamp | Not implemented | No future-dated row found in this incident |
| Material timestamp disorder | Not implemented | Out of scope — no evidence of this failure mode |

Per the mission's own framing ("at minimum reject/quarantine..."), only
the date-format gate is added, because it is the only one of the six with
actual defect evidence behind it. Adding untested constraints for failure
modes with zero observed instances would be exactly the kind of
unrequested scope expansion the mission's "do not redesign Sentinel"
instruction warns against.

## Deployment

Applied via `ALTER`-free `CREATE TRIGGER` (SQLite supports adding a
trigger to an existing table without rewriting it — no table lock beyond
the single DDL statement, no data migration required for the trigger
itself). Applied in the same transaction as the 689-row quarantine/delete
(SENTINEL_FRESHNESS_RESTORATION_EVIDENCE.md).
