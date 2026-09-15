# DAT.AI Charter

**Status**: GROUNDED — reflects verified Phase C state, not aspiration.
**Last updated**: 2026-08-27 (DAT.AI Phase C canonical recovery)

## Scope

DAT.AI is NEXUS's Land / Geospatial Intelligence institution. Its charter,
per the founding directive: "Semi-autonomous land, planning, property,
cadastral and geospatial intelligence institution."

## What currently exists (verified, not claimed)

| Capability | Status |
|---|---|
| Zoning model + spatial API | IMPLEMENTED, TESTED (unit + integration, dual PostGIS/SQLite dialect support) |
| Zoning data ingestion pipeline | IMPLEMENTED, TESTED |
| ML model registry | IMPLEMENTED, TESTED |
| Model promotion gate | IMPLEMENTED, TESTED |
| Model-status fail-closed enforcement | IMPLEMENTED, TESTED (untrained checkpoint cannot be promoted, verified by regression test) |
| Anti-fabrication test suite | IMPLEMENTED, TESTED (6 of 8 sub-tests active; 2 deferred pending satellite/planet.py recovery) |
| NEXUS institutional message contract | IMPLEMENTED, TESTED (schema validation only; not yet wired to any message bus or executive kernel) |
| Satellite acquisition / classification / training | NOT RECOVERED this phase — requires CDSE/Planet credentials confirmed absent from this estate |
| Valuation intelligence | NOT PORTED — genuine rule-based logic exists in donor `source/`, untested, not yet integrated |
| Opportunity scoring, infrastructure impact modeling | DO NOT EXIST anywhere in this estate |

## Non-scope (explicitly)

DAT.AI does not perform global executive reasoning, cross-institution
priority allocation, or resource-economy accounting — those are NEXUS
executive-kernel responsibilities (which do not yet exist in canonical
NEXUS either; see `FEDERATION_LINEAGE_GAP_MATRIX.md`).

## Current maturity

**INTEGRATED** (per the directive's capability lifecycle: PLANNED →
IMPLEMENTED → TESTED → **INTEGRATED** → EMPIRICALLY_VALIDATED → RESILIENT →
OPERATIONAL). Not EMPIRICALLY_VALIDATED: the model checkpoint is proven
untrained: the zoning provenance claim ("confidence 0.95") is a declared
constant, not a verified per-record score. Not OPERATIONAL: no institution
currently consumes DAT.AI's output.

## Governing documents

See `DATAI_LIMITATIONS.md` for the complete, current list of what is not yet
true. See `DATAI_PHASE_D_ENTRY_CRITERIA.md` for the next bounded mission.
