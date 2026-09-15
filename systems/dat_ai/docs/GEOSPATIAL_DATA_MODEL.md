# Geospatial Data Model (DAT.AI)

**Status**: GROUNDED — schema verified against a live disposable PostGIS instance during Phase C.

## PlanningZone (primary canonical model, `app/models/zoning.py`)

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| project_id | String(100), unique, indexed | administrative identifier |
| project_name | String(500) | |
| administrative_code | String(50), indexed | |
| name, zone_type, description | String/Text | original schema fields |
| zone_category | String(100), indexed | normalized land-use classification |
| sub_categories | JSONB (JSON on SQLite) | |
| geom | Geometry(POLYGON, SRID 4326) | GIST-indexed; `spatial_index=False` on the column itself, index declared explicitly in `__table_args__` — the correct pattern (see `GEOSPATIAL_STORAGE_ARCHITECTURE.md`) |
| data_confidence | Float, default 0.95 | **DECLARED_SOURCE_CONFIDENCE, not verified** — see `SPATIAL_PROVENANCE_STANDARD.md` |
| validation_status | String(50), default `"ingested"` | never yet progresses to `"accepted"`/`"rejected"` in the current ingestion path |
| source_url | Text | genuine per-record provenance link |
| ingestion_date, created_at, updated_at | DateTime | |

## Listing (`app/models/listings.py`)

Referenced by zoning intersection queries (`/zoning/zones/intersect/property/{listing_id}`). Not itself a DAT.AI-owned entity — shared with the broader property-listing surface (scrapers, not recovered this phase).

## SatelliteLayer / SatelliteChange / SatelliteProduct / SatelliteAsset / SatelliteProcessingRun / SatelliteValidation / PlanetImagery / SatellitePhoto / ModelMetrics / SatelliteIngestLog (`app/models/satellite.py`)

Present, migrated, tested at the schema level (12 ORM tables create cleanly
via `Base.metadata.create_all()` — the Phase C fix for the spatial-index
duplication defect is verified here). Not yet API-exposed in canonical
NEXUS (see `LAND_INTELLIGENCE_ARCHITECTURE.md`).

## Canonical fields per the directive's required minimum (§12 of the Phase C mission)

| Required field | Present as | Status |
|---|---|---|
| geometry | `geom` (Geometry, SRID 4326) | ✅ |
| CRS/SRID | 4326 throughout | ✅ |
| source identifier | `project_id`, `stac_id` (satellite) | ✅ |
| source URL | `source_url` | ✅ |
| ingestion timestamp | `ingestion_date` | ✅ |
| observation timestamp | `observation_date` (satellite layers only; not present on PlanningZone) | ⚠️ PARTIAL — zoning has no distinct "observed at" vs "ingested at" split; unknown, not invented |
| provenance status | `validation_status` | ✅ (mechanism exists; workflow not yet exercised past `"ingested"`) |
| declared confidence | `data_confidence` | ✅ (see provenance standard for honest interpretation) |
| verified confidence if later derived | **DOES NOT EXIST** | ❌ MISSING — no column distinguishes a declared vs. independently-verified confidence. This is an honest gap, not filled with an invented value. |
| data lineage | `source_url` + satellite provenance columns (`source_product_id`, `run_id`, `preprocessing_version`, `model_sha256`) | ✅ for satellite; ⚠️ PARTIAL for zoning (source_url only, no ingestion-run linkage) |
| entity type | `zone_category`, `zone_type` | ✅ |
| jurisdiction | `administrative_code` (partial — Vietnamese administrative code, not a formal jurisdiction hierarchy) | ⚠️ PARTIAL |
| validity interval | **DOES NOT EXIST** | ❌ MISSING — no `valid_from`/`valid_to` on PlanningZone; a zone's temporal applicability is unknown |
| canonical ID | `id` (surrogate) + `project_id` (natural, unique) | ✅ |

**Per mission instruction: unknown values are left unknown, not invented.** The ❌/⚠️ rows above are the honest current gaps, not filled with fabricated data.
