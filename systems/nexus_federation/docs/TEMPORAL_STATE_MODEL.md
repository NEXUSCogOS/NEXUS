# Temporal State Model

**Status**: GROUNDED. `state/temporal.py`, exercised by `tests/unit/test_temporal.py` and `tests/temporal/test_kernel_ordering.py`.

## Classifications

`CURRENT`, `STALE`, `EXPIRED`, `OUT_OF_ORDER`, `DUPLICATE`, `CLOCK_SKEW_REJECTED`.

## The one function

`classify_incoming_report()` is the sole decision point. Order of checks,
and why:

1. **Clock skew** (`MAX_CLOCK_SKEW = 5 minutes`) — checked first; a
   report claiming to be from the future is suspicious regardless of
   anything else.
2. **Duplicate** (same `cycle_id` as the currently-accepted report) —
   idempotent accept, no new state transition.
3. **Out-of-order** (older timestamp than currently-accepted) — rejected;
   *an older report can never overwrite newer accepted state*, full stop.
4. **Staleness of the incoming report itself** against wall-clock `now`:
   `STALE_THRESHOLD = 1 hour`, `EXPIRED_THRESHOLD = 24 hours`.

## Stale state stays visibly stale

`classify_age_only()` re-derives a classification from a persisted
timestamp at *query* time, independent of when the report was originally
ingested — proven by `tests/restart/test_restart_recovery.py::
test_stale_state_becomes_stale_correctly_across_restart` to survive a
process restart with zero new reports. Nothing here silently treats old
accepted state as fresh just because no newer report has arrived.

## Verified

All six classifications independently tested against both the pure
function (`tests/unit/test_temporal.py`) and the full kernel pipeline
(`tests/temporal/test_kernel_ordering.py`, `tests/failure/test_failure_modes.py`
#6-#8). An out-of-order report was proven, empirically, not to corrupt the
registry's already-accepted newer state.
