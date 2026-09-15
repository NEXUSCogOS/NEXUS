# EVIDENCE RESOLUTION LEDGER SPEC
**NEXUS Federation F2 — 2026-08-27**

## CURRENT VERIFIED IMPLEMENTATION

`persistence/db.py: evidence_resolution_ledger` is an append-only table
(no update method exists) recording every resolution ATTEMPT:
`resolution_id, timestamp, institution, mission_id, cycle_id,
evidence_ref, expected_hash, observed_hash, existence,
verification_result, reason, resolver_version`.

`verification_result` reuses `provenance.model.VerificationStatus`:
`VERIFIED | PARTIAL | UNVERIFIED | INVALID | MISSING`. Assignment logic
(`kernel.py`, per evidence ref per capability, every ingest):

- not resolved at all -> `MISSING`
- resolved, no prior baseline (first sighting) -> `PARTIAL` (existence
  confirmed, but nothing to independently corroborate the hash against
  yet)
- resolved, baseline exists, hash matches -> `VERIFIED`
- resolved, baseline exists, hash differs -> `INVALID` (drift)

Every one of these is written every time, regardless of outcome — a
`MISSING` or `INVALID` result is never silently discarded or overwritten
by a later successful resolution; `get_evidence_resolution_history()`
returns the full, ordered, immutable sequence.

### Proven: VALID -> DRIFT -> RESTORED, full history preserved

`tests/evidence/test_evidence_ledger.py::test_valid_evidence_then_drift_then_restore_preserves_full_history`:
1. A file is hashed and a baseline recorded (`PARTIAL`).
2. The file is modified; a fresh resolution's hash differs from the
   baseline (`INVALID`).
3. The file is restored to its original content; the fresh hash matches
   the baseline again (`VERIFIED`).

All three ledger rows persist afterward — the `INVALID` row is never
deleted or mutated by the later `VERIFIED` one.

### Proven: real kernel usage produces one row per ingest attempt

`test_kernel_records_drift_via_ledger_across_two_ingests`: two real
`kernel.ingest_report()` calls against the same evidence_ref produce
exactly two ledger rows, `cycle_id` correctly distinguishing them.

## TARGET

- A periodic reconciliation job that re-resolves every evidence_ref an
  institution has ever referenced, on a schedule, independent of new
  reports arriving — so drift is detected even for evidence nobody has
  re-cited recently.
- A dedicated `provenance_failures`/`evidence_drift_events` dashboard
  (the counters already exist in `observability/counters.py`, derived
  directly from this ledger — a real UI consuming them does not exist
  yet).

## LIMITATIONS

- `expected_hash` is the baseline recorded on FIRST sighting, not an
  independently-supplied expected value from the institution itself (the
  institution's own contract carries no expected-hash field — see
  `evidence/resolver.py`'s own documented limitation, unchanged since F1).
  This means a maliciously-substituted file present on the VERY FIRST
  resolution would be silently accepted as the baseline — the ledger
  detects drift AFTER first sighting, not compromise AT first sighting.
