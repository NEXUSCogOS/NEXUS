# DAT.AI Evidence Standard

**Status**: GROUNDED — describes mechanisms that were actually exercised this phase, with explicit note of what remains unverified.

## Evidence mechanisms that exist and were exercised

1. **`app.ml.satellite_classifier.audit_checkpoint()`** — runs real
   inspection of a model checkpoint's tensors (conv1 channel count,
   bit-for-bit comparison against stock ImageNet weights, head-initialization
   statistics) and returns a `ModelAudit` with concrete findings. Exercised
   directly against the real 94.4MB checkpoint in both Phase A+B and Phase C;
   see `DATAI_MODEL_STATUS_REGISTER.md`.
2. **`/readiness` endpoint** — computes 8 independent component states
   (database, postgis, migrations, classifier, satellite_ingestion,
   satellite_scheduler, planet_validation, configuration) from live checks
   at request time, not a cached/assumed value. Cross-validated against this
   mission's own independent findings (both agree migration state and model
   state).
3. **Migration `schema_migrations` table** — a real, queryable record of
   which migrations actually committed, used by `_check_migrations()` and
   by this mission's own verification (confirmed `002`, `003`, `005` recorded
   after the Phase C fixes, where `003` previously failed to record itself
   before the fix).
4. **Provenance columns** (`source_url`, `source_product_id`, `run_id`,
   `model_sha256`, `data_class`) — real, queryable, enforced by CHECK
   constraints (migration 002/003) for the `observed`/`derived`/`synthetic`/
   `test` vocabulary.
5. **`institutional/contract.py`** — schema-validates every report; a
   malformed message (e.g., `escalation_reason` set without the flag) raises
   rather than silently passing, per directive §6 fail-closed requirement.
   Verified by `tests/unit/test_institutional_contract.py`.

## What is NOT yet an evidence mechanism (honest gap, not filled)

- No field distinguishes a *declared* vs. *independently verified* spatial
  confidence score (see `SPATIAL_PROVENANCE_STANDARD.md`).
- No row-level provenance audit has been run against real ingested zoning
  data (schema-level provenance is verified; data-level is not).
- No cross-institution evidence exchange exists — `institutional/reporter.py`
  produces valid envelopes that nothing currently consumes.

## Evidence artifacts produced this phase (for audit trail continuity)

`DATAI_RECOVERY_PROVENANCE.json`, `DATAI_CANONICAL_TEST_BASELINE.md`, and
the git commit `b6da4fc` itself (with its detailed commit message) together
form the evidence record for this recovery. Prior-phase evidence
(`DATAI_DONOR_FORENSIC_REPORT.md`, `DATAI_PHASE_AB_VERIFICATION_REPORT.md`,
etc.) remains the evidentiary basis for claims about the donor state before
recovery.
