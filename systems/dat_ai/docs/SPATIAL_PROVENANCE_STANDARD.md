# Spatial Provenance Standard (DAT.AI)

**Status**: GROUNDED — this document exists because Phase A+B and Phase C
found and corrected a specific, real provenance-labeling error. It records
the corrected standard, not an aspirational one.

## The corrected standard

**`data_confidence` on `PlanningZone` (and equivalent fields elsewhere) is a
DECLARED_SOURCE_CONFIDENCE, not a verified per-record score, unless and
until a separate, independently-computed verified-confidence field exists
(it does not yet — see `GEOSPATIAL_DATA_MODEL.md`).**

### What was found (evidence, not assertion)

`worker/tasks/ingest_zoning_data.py`:
```python
confidence = float(argv[2]) if len(argv) > 2 else 0.95
...
values = {..., "data_confidence": confidence, "validation_status": "ingested", ...}
```

`confidence` is a single flat value applied to **every row in one ingestion
run** — a CLI argument or its hardcoded fallback, never computed per-record
from any per-record signal (source cross-agreement, completeness, an actual
authentication response). The donor's original docstring read "Data source:
Vietnamese government planning databases (DVHC authenticated). Confidence:
0.95 (authoritative reference data)" — worded as if this were a verified
measurement. No DVHC-specific authentication call was found anywhere in the
ingestion code path.

### What genuinely IS verified per-record

`source_url` (`record.get("sourceUrl")`) is captured per record and is real,
traceable provenance — distinct from the confidence question, and not
affected by this correction.

## The standard, going forward

1. Any field whose value is set identically across an entire batch/run MUST
   be documented as a **declared** value (a stated assumption or input), not
   a **verified** one.
2. A **verified** confidence/quality field requires evidence that it was
   computed or checked per-record — cross-source agreement, an
   authentication response, an independent audit. If no such mechanism
   exists, do not add a field that implies one.
3. Documentation, code comments, and API responses must use the same
   epistemic class consistently. This standard was violated (docstring said
   "authoritative reference data," code delivered a flat constant) and is
   now corrected in `app/models/zoning.py` and `migrations/005_extend_planning_zones.sql`.
4. `validation_status` (`pending`/`accepted`/`rejected`/`ingested`) is a real,
   enforced-at-the-database-level vocabulary (see migration 002's CHECK
   constraints for `listings`, and the equivalent zoning field) — but the
   current zoning ingestion path never progresses a row past `"ingested"`.
   Do not present `"ingested"` as equivalent to `"accepted"`.

## Where this applies today

- `app/models/zoning.py::PlanningZone.data_confidence`
- `migrations/005_extend_planning_zones.sql` (COMMENT ON COLUMN, corrected)
- `institutional/reporter.py` (explicitly lists this as a `risk` in every
  generated report — see `DATAI_INSTITUTIONAL_CONTRACT.md`)

## Verification status of the underlying Dong Nai zoning data

**Row-level provenance was not independently checked against real ingested
data this phase** (Phase A+B deferred this to avoid treating disposable-test
data as production evidence; Phase C's disposable database also did not
ingest the real zoning file end-to-end as part of its regression tests).
This remains an open item — see `DATAI_PHASE_D_ENTRY_CRITERIA.md`.
