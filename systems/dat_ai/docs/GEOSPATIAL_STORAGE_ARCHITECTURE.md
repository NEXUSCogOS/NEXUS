# Geospatial Storage Architecture (DAT.AI)

**Status**: GROUNDED. See `DATAI_CANONICAL_STORAGE_MAP.md` for the full placement matrix; this document covers the database/schema layer specifically.

## Bootstrap order (verified during Phase C)

```
1. Base.metadata.create_all(engine)   -- creates all 12 ORM tables
2. migrations/002_provenance_and_governance.sql   -- idempotent, safe to re-run
3. migrations/003_satellite_provenance.sql        -- idempotent (Phase C fix), safe to re-run
4. migrations/004_create_planning_zones_base.sql  -- idempotent
5. migrations/005_extend_planning_zones.sql       -- idempotent (Phase C fix)
```

`migrations/retired/001_satellite_tables.sql.retired` is preserved for
historical reference and MUST NOT be run — it predates the ORM, is fully
superseded, and references a `valuation_history` table that no longer
exists anywhere in the schema. See `migrations/retired/RETIREMENT_NOTE.md`.

This bootstrap sequence was verified end-to-end against a disposable
PostgreSQL 18.3 + PostGIS 3.6.4 instance during Phase C: all 5 active
migrations (002-005, in order, twice — once from a bare ORM-created schema,
once re-applied to prove idempotency) completed cleanly with `INSERT 0 1`
or `INSERT 0 0` on their `schema_migrations` tracking row.

## Spatial index discipline

Every `Geometry(...)` column on a table that also declares an explicit
`Index(...)` in `__table_args__` must set `spatial_index=False` on the
column itself. `zoning.py`'s `PlanningZone.geom` established this pattern
first (with an explanatory comment); `satellite.py`'s `SatelliteLayer.geom`
and `SatelliteChange.geom` did not follow it and caused a `DuplicateTable`
error on `create_all()` — fixed in Phase C. **Any future Geometry column
added to this codebase must follow the `zoning.py` pattern.**

## Storage placement (see `DATAI_CANONICAL_STORAGE_MAP.md` for full detail)

- Live PostGIS database: LOCAL_HOT for control/connection state; the
  database's own data directory placement (local vs. external) was
  **not** decided this phase — Phase A+B explicitly deferred that
  decision pending a crash-recovery test on external filesystems, and
  Phase C did not revisit it (out of scope: Phase C recovers code, not
  infrastructure placement).
- Model weights: EXTERNAL_ACTIVE, referenced via `MODEL_PATH` env var,
  never duplicated into canonical NEXUS (see `models/MODEL_REGISTRY_METADATA.json`).
- Zoning data (`data/zoning/`, `data/zoning_raw/`): small (~10KB each),
  tracked in canonical git as test fixtures for the ingestion pipeline —
  an explicit, justified exception to "large GIS datasets → external,"
  since 10KB is not large and duplication cost is negligible.
- Satellite cache, labeled datasets, logs: excluded via `.gitignore`,
  external-first by design (matches the donor's own convention).
