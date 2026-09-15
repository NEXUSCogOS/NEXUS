# PROCESS RECOVERY PROTOCOL
**NEXUS Federation F2 — 2026-08-27**

## CURRENT VERIFIED IMPLEMENTATION

### Real OS-process restart
`tests/restart/test_subprocess_restart.py` spawns two genuinely separate
OS processes (`subprocess.run`, not same-process object recreation):
Process A ingests one report with a relevance signal and exits completely;
Process B starts as a fresh interpreter, loads the same SQLite file, and
verifies:

| Requirement | Verified by |
|---|---|
| Institution state survives | `checks["institution_state_survives"]` |
| Accepted cycle survives | `checks["accepted_cycle_survives"]` |
| Evidence links survive | `checks["evidence_links_survive"]` (real sha256, 64 hex chars) |
| Temporal ordering survives | `classify_age_only()` re-derived from the persisted timestamp alone |
| Duplicate report recognized | `checks["duplicate_recognized"]` |
| Duplicate delegation not regenerated | `checks["duplicate_delegation_not_generated"]` |

Real, distinct PIDs were captured on the run this document is based on
(see `FEDERATION_PROCESS_RECOVERY_EVIDENCE.md` for the exact values). A
`process_recovery` observability event is recorded by Process B — durably,
in `observability_event_log` — but ONLY after every check above passed;
this is never recorded speculatively or by convention.

### Crash-point recovery
`tests/crash/test_crash_point_recovery.py` covers the five named
transaction points. The key structural fix underlying this (NEXUS
Federation F2, `persistence/db.py: FederationStore.commit_accepted_cycle`)
closes a real gap that existed in F1: F1 wrote `report_log`, the registry
upsert, and (F2's new) state events as three independently-committed
writes. A crash between the first and the other two could leave
`report_log` showing a cycle as accepted while `institution_registry`
still held the prior state — and because a subsequent retry of that same
`cycle_id` would then be classified `DUPLICATE` (which correctly never
re-runs evidence resolution), the registry would freeze on stale state
**forever**, silently.

F2 fix: `report_log` + `institution_registry` + `state_event_log` are
written in ONE SQLite transaction (`commit_accepted_cycle`). A crash
before that transaction commits leaves NO trace of the cycle in any of the
three tables — a retry is correctly classified `CURRENT` (not
`DUPLICATE`) and reprocesses the cycle from scratch. A crash after it
commits leaves all three durably consistent, and a retry is correctly
classified `DUPLICATE`.

| Crash point | Test | Outcome proven |
|---|---|---|
| 1. After receipt, before accept/reject decision | `test_crash_point_1_after_receipt_before_acceptance` | Nothing persisted; retry behaves as first-ever ingest |
| 2. After evidence resolution, before state persistence | `test_crash_point_2_after_evidence_resolution_before_state_persistence` | Evidence-ledger/provenance audit rows exist (the attempt happened); registry/report_log/state_events are untouched; retry is `CURRENT`, fully reprocesses |
| 3. After state persistence, before delegation | `test_crash_point_3_after_state_persistence_before_delegation` | Cycle durably accepted; retry is `DUPLICATE`; the missing delegation is produced exactly once on retry |
| 4. Before delegation persistence | `test_crash_point_4_before_delegation_persistence_no_duplicate_on_retry` | Exactly one delegation results after any number of retries |
| 5. After delegation persistence | `test_crash_point_5_after_delegation_persistence_fully_recovered_state` | Retry (duplicate) shows byte-identical final state, no phantom second delegation |

Evidence-resolution ledger rows, evidence baselines, and provenance
records are intentionally NOT inside the atomic transaction: they are
additive, attempt-scoped audit rows, not canonical current state, so it is
correct (and required by "every attempt is recorded, never overwritten")
for them to accumulate across a crashed-then-retried attempt.

## TARGET

- A crash-injection harness that can interrupt a REAL subprocess (not
  just monkeypatch a function) at an arbitrary byte offset in execution —
  e.g. via `SIGKILL` sent at a controlled instant — for even stronger
  confidence than function-level monkeypatching provides.
- Automatic reconciliation tooling that scans for any report_log row with
  no matching registry state (should be structurally impossible after
  this fix, but a periodic integrity check would make that guarantee
  observable in production, not just in tests).

## LIMITATIONS

- The crash-point tests interrupt via monkeypatched exceptions at known
  call boundaries, not via an actual signal delivered to a real process at
  an arbitrary point. This proves the code's OWN transaction boundaries
  are safe; it does not prove safety against a crash mid-write at the
  SQLite/OS level (SQLite's own WAL durability guarantees are relied upon
  for that, not re-verified here).
- Process B's rebuild of the identical payload in
  `tests/restart/_subprocess_helpers/process_b.py` requires the exact
  timestamp Process A used to be passed as an argument — a real deployed
  system would need the ORIGINAL payload (or its hash) persisted
  somewhere for a genuine retry, not reconstructed from scratch.
