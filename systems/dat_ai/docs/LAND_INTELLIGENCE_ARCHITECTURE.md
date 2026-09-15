# Land Intelligence Architecture (DAT.AI)

**Status**: GROUNDED. Reflects `systems/dat_ai/` as committed in Phase C (commit `b6da4fc`).

## Current architecture (as built, code-verified)

```
FastAPI app (app/main.py)
  ├── routes/health.py   -- /health /liveness /readiness (multi-component, evidence-derived)
  └── routes/zoning.py   -- /zoning/zones, /zoning/stats, /zoning/zones/intersect/*, /zoning/zones/{id}
        │
        ├── models/zoning.py (PlanningZone ORM, PostGIS + SQLite dual-dialect)
        ├── models/listings.py (Listing ORM, referenced by zoning intersection queries)
        └── models/satellite.py (SatelliteLayer/Change/Product/etc — schema present,
                                   not yet API-exposed in canonical; see below)

worker/tasks/ingest_zoning_data.py -- zoning ingestion pipeline (tested)

app/ml/
  ├── model_registry.py       -- version tracking, promote/reject workflow
  ├── promotion_gate.py       -- metric-threshold gated promotion
  ├── production_readiness.py -- readiness scoring
  ├── inference_gates.py      -- inference-time gating
  └── satellite_classifier.py -- audit_checkpoint()/audit_only() (model status enforcement)

institutional/
  ├── contract.py  -- NEXUS institutional message envelope (pydantic schema + validation)
  └── reporter.py  -- builds a real report from live health checks
```

## What is deliberately NOT wired yet

`app/models/satellite.py` (12 ORM tables covering satellite products, assets,
processing runs, layers, changes, validations) is present and its schema is
fully migrated (see `GEOSPATIAL_STORAGE_ARCHITECTURE.md`), because
`app/ml/satellite_classifier.py`'s model-audit function depends on it and
because 2 of the 3 Phase C defects live in its ORM definitions. But no
route exposes it (routes/satellite.py, routes/properties.py, routes/tiles.py,
the full satellite acquisition pipeline, and scheduler.py were not recovered
— they require CDSE/Planet credentials confirmed absent from this estate).
This is intentional scope discipline, not an oversight: see
`DATAI_COMPONENT_RECOVERY_MATRIX.md` (prior mission) for the MODERNIZE
classification and `DATAI_PHASE_D_ENTRY_CRITERIA.md` for when it's revisited.

## Data flow (current, verified)

```
Real Dong Nai zoning export (data/zoning_raw/dong_nai_2024.json)
        │
        ▼
worker/tasks/ingest_zoning_data.py  (parses geometry, applies a flat
        │                            per-batch confidence constant --
        │                            see SPATIAL_PROVENANCE_STANDARD.md)
        ▼
planning_zones table (PostGIS, SRID 4326, GIST-indexed)
        │
        ▼
app/routes/zoning.py  (spatial intersection queries, dual PostGIS/Shapely
        │              backend depending on dialect)
        ▼
HTTP JSON response (includes `spatial_backend` field on list/stats/
                     intersection responses; NOT on the single-zone detail
                     response -- see DATAI_PHASE_C_RECOVERY_REPORT.md for
                     why that's a known, pre-existing, out-of-scope test
                     expectation mismatch, not a missing feature)
```

## Integration points (per directive, implemented this phase only as a contract)

See `DATAI_INSTITUTIONAL_CONTRACT.md`. No cross-institution orchestration
exists yet — NEXUS has no executive kernel or message bus for DAT.AI to
report into (confirmed in the prior `FEDERATION_LINEAGE_GAP_MATRIX.md`
mission). `institutional/reporter.py` produces a valid envelope; nothing
consumes it.
