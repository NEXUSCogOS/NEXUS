# DAT.AI Limitations

**Status**: GROUNDED. This is the single most important document for anyone
about to build on top of DAT.AI — read it before trusting any output.

## Model

- The satellite land-use classifier checkpoint (`satellite_classifier_v1.2.pth`)
  is **bit-identical to stock, untrained ImageNet ResNet-50 weights** with a
  freshly-initialized classification head. It has never been trained on
  satellite imagery. `app.ml.satellite_classifier.audit_checkpoint()` proves
  this and refuses to let it be promoted regardless of configuration.
- No satellite inference capability exists in canonical NEXUS today (the
  acquisition/inference pipeline was not recovered this phase).

## Data provenance

- Zoning `data_confidence` (default 0.95) is a **declared, per-batch constant**,
  not a verified per-record score. See `SPATIAL_PROVENANCE_STANDARD.md`.
- No DVHC (Vietnamese administrative authentication) verification call
  exists in the ingestion code, despite the donor's original docstring
  implying one. Corrected in Phase C.
- Row-level provenance of the real Dong Nai zoning data has not been
  independently audited against actual ingested rows.
- Licensing status of the Vietnamese government zoning data is unknown.

## Coverage

- Only Dong Nai province has any zoning data (a 10KB test fixture).
- `validation_status` never progresses past `"ingested"` in the current
  ingestion path — the `pending`→`accepted`/`rejected` workflow the schema
  supports is not yet exercised by any real code path.

## Capabilities that do not exist anywhere in this estate

- Valuation intelligence (real rule-based logic exists in the donor's
  `source/` directory, untested, not integrated, not ported this phase)
- Land opportunity scoring
- Infrastructure impact modeling
- Development constraint modeling (beyond what zoning categories imply)
- A formal zoning ontology document (the data model exists; a category
  hierarchy/ontology document does not)

## Integration

- No NEXUS executive kernel or institutional message bus exists to consume
  DAT.AI's institutional reports — `institutional/reporter.py` produces
  valid envelopes that nothing currently reads.
- No other NEXUS institution (Sentinel, Librarian, News, YouTube) has any
  code-level integration with DAT.AI.

## Testing

- 1 integration test (`test_against_real_postgis`) fails on a pre-existing,
  precisely-diagnosed stale assertion (expects `spatial_backend` on a
  single-zone detail response that, by design, doesn't carry that field —
  only list/stats responses do). Not fixed this phase (out of the 3 assigned
  defects); see `DATAI_CANONICAL_TEST_BASELINE.md`.
- 3 tests are correctly skipped (satellite acquisition pipeline dependency,
  Phase D scope).
- No test has ever exercised DAT.AI against real CDSE/Planet credentials or
  real network access.

## Storage

- Whether PostGIS's live data directory is safe on an external (APFS)
  filesystem was never empirically tested (crash-recovery test deferred in
  Phase A+B, not revisited in Phase C). Default to local disk for the live
  database until that test is run.

## What this document does NOT cover

Limitations of the broader NEXUS estate (credential availability, other
institutions' maturity) are covered in `FEDERATION_LINEAGE_GAP_MATRIX.md`
and the Phase 1A storage audit, not repeated here.
