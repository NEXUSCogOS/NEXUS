-- Migration 003: satellite product/asset/run provenance
--
-- Purpose
--   Make every derived satellite record traceable to the exact source product,
--   bands, model checkpoint, preprocessing code version and pipeline run that
--   produced it. Before this migration a row in satellite_layers could not
--   answer "which image is this from?".
--
-- Safety
--   Additive only. No historical table is dropped or rewritten. All column
--   additions use IF NOT EXISTS. Existing rows are unaffected (there are none
--   in the satellite tables at time of writing, verified via check-db).
--
-- Created: 2026-08-14
--
-- Phase C fix (2026-08-27, DAT.AI Phase C canonical recovery, defect 2):
--   Section 9 (labelling legacy `properties` rows as synthetic) referenced a
--   table that does not exist on any fresh/canonical deployment -- it only
--   exists on installations that previously ran the retired
--   worker/db.py::ensure_schema() or ops/init_db.sql bootstrap paths. This
--   caused the migration to fail outright on a clean database (confirmed in
--   DAT.AI Phase A+B verification). Section 9 is NOT dead code -- its purpose
--   (honestly labelling pre-existing synthetic seed data as synthetic,
--   without deleting it) is legitimate and must be preserved for any
--   deployment where `properties` genuinely exists. The fix wraps it in an
--   existence guard so it is a safe no-op on fresh databases and still does
--   its job on old ones. See DATAI_DEFECT_REPAIR_EVIDENCE.md for the full
--   evidence chain, including confirmation via routes/tiles.py that the
--   string 'properties' used there is an MVT layer-name label, not a
--   reference to this table.

BEGIN;

-- =====================================================================
-- 1. satellite_products — one row per discovered STAC item
--    Discovery is metadata only; presence here does NOT imply imagery was
--    downloaded. That is tracked per-asset in satellite_assets.
-- =====================================================================
CREATE TABLE IF NOT EXISTS satellite_products (
  id                BIGSERIAL PRIMARY KEY,
  stac_id           VARCHAR(255) NOT NULL UNIQUE,
  collection        VARCHAR(100) NOT NULL,
  catalogue_url     TEXT NOT NULL,
  mgrs_tile         VARCHAR(20),
  grid_code         VARCHAR(50),
  platform          VARCHAR(50),
  processing_level  VARCHAR(20),
  product_type      VARCHAR(50),
  sensed_at         TIMESTAMP NOT NULL,
  cloud_cover       DOUBLE PRECISION,
  geom              GEOMETRY(POLYGON, 4326),
  bbox_min_lon      DOUBLE PRECISION,
  bbox_min_lat      DOUBLE PRECISION,
  bbox_max_lon      DOUBLE PRECISION,
  bbox_max_lat      DOUBLE PRECISION,
  aoi_name          VARCHAR(100),
  asset_inventory   JSONB,
  discovered_at     TIMESTAMP NOT NULL DEFAULT NOW(),
  created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_products_cloud
    CHECK (cloud_cover IS NULL OR (cloud_cover >= 0 AND cloud_cover <= 100))
);

CREATE INDEX IF NOT EXISTS idx_products_stac ON satellite_products(stac_id);
CREATE INDEX IF NOT EXISTS idx_products_tile ON satellite_products(mgrs_tile);
CREATE INDEX IF NOT EXISTS idx_products_sensed ON satellite_products(sensed_at DESC);
CREATE INDEX IF NOT EXISTS idx_products_aoi ON satellite_products(aoi_name);
CREATE INDEX IF NOT EXISTS idx_products_geom ON satellite_products USING GIST(geom);

-- =====================================================================
-- 2. satellite_assets — one row per file that GENUINELY EXISTS on disk
--    A row here means bytes were transferred and checksummed. There is no
--    status column because there is no such thing as a half-present asset:
--    if it is not verified, it is not recorded.
-- =====================================================================
CREATE TABLE IF NOT EXISTS satellite_assets (
  id              BIGSERIAL PRIMARY KEY,
  product_id      BIGINT NOT NULL
                    REFERENCES satellite_products(id) ON DELETE CASCADE,
  asset_key       VARCHAR(50) NOT NULL,
  band_name       VARCHAR(20),
  resolution_m    INT,
  source_uri      TEXT NOT NULL,
  transport       VARCHAR(20) NOT NULL,
  local_path      TEXT NOT NULL,
  size_bytes      BIGINT NOT NULL,
  sha256          CHAR(64) NOT NULL,
  raster_crs      VARCHAR(100),
  raster_width    INT,
  raster_height   INT,
  raster_transform DOUBLE PRECISION[],
  downloaded_at   TIMESTAMP NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_assets_product_key UNIQUE (product_id, asset_key),
  CONSTRAINT chk_assets_size CHECK (size_bytes > 0),
  CONSTRAINT chk_assets_transport CHECK (transport IN ('s3', 'https'))
);

CREATE INDEX IF NOT EXISTS idx_assets_product ON satellite_assets(product_id);
CREATE INDEX IF NOT EXISTS idx_assets_key ON satellite_assets(asset_key);

-- =====================================================================
-- 3. satellite_processing_runs — one row per pipeline invocation
-- =====================================================================
CREATE TABLE IF NOT EXISTS satellite_processing_runs (
  id                      BIGSERIAL PRIMARY KEY,
  run_id                  UUID NOT NULL UNIQUE,
  runtime_mode            VARCHAR(20) NOT NULL,
  aoi_name                VARCHAR(100),
  started_at              TIMESTAMP NOT NULL DEFAULT NOW(),
  finished_at             TIMESTAMP,
  status                  VARCHAR(30) NOT NULL DEFAULT 'running',
  gate_reached            VARCHAR(50),
  products_discovered     INT NOT NULL DEFAULT 0,
  products_acquired       INT NOT NULL DEFAULT 0,
  products_classified     INT NOT NULL DEFAULT 0,
  layers_written          INT NOT NULL DEFAULT 0,
  changes_written         INT NOT NULL DEFAULT 0,
  bytes_downloaded        BIGINT NOT NULL DEFAULT 0,
  model_version           VARCHAR(50),
  model_sha256            CHAR(64),
  model_promotion_status  VARCHAR(50),
  preprocessing_version   VARCHAR(50),
  code_version            VARCHAR(100),
  failure_class           VARCHAR(50),
  error_message           TEXT,
  notes                   JSONB,
  CONSTRAINT chk_runs_mode
    CHECK (runtime_mode IN ('development','test','commissioning','production')),
  CONSTRAINT chk_runs_status
    CHECK (status IN ('running','succeeded','failed','aborted','dry_run'))
);

CREATE INDEX IF NOT EXISTS idx_runs_started
  ON satellite_processing_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status
  ON satellite_processing_runs(status);

-- =====================================================================
-- 4. Provenance columns on satellite_layers
--    Real foreign keys, because a real relational link now exists: a layer
--    IS derived from exactly one product by exactly one run.
-- =====================================================================
ALTER TABLE satellite_layers
  ADD COLUMN IF NOT EXISTS source_product_id BIGINT
    REFERENCES satellite_products(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS run_id UUID,
  ADD COLUMN IF NOT EXISTS preprocessing_version VARCHAR(50),
  ADD COLUMN IF NOT EXISTS model_sha256 CHAR(64),
  ADD COLUMN IF NOT EXISTS model_promotion_status VARCHAR(50),
  ADD COLUMN IF NOT EXISTS observation_date DATE,
  ADD COLUMN IF NOT EXISTS cloud_cover DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS area_sqm DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS pixel_count INT,
  ADD COLUMN IF NOT EXISTS source_crs VARCHAR(100),
  ADD COLUMN IF NOT EXISTS data_class VARCHAR(20) NOT NULL DEFAULT 'derived',
  ADD COLUMN IF NOT EXISTS quality_flags JSONB;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'chk_layers_data_class') THEN
    ALTER TABLE satellite_layers
      ADD CONSTRAINT chk_layers_data_class
      CHECK (data_class IN ('observed','derived','synthetic','test'));
  END IF;

  -- Derived land-use output must never be recorded as a direct observation.
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'chk_layers_promotion') THEN
    ALTER TABLE satellite_layers
      ADD CONSTRAINT chk_layers_promotion
      CHECK (model_promotion_status IS NULL
             OR model_promotion_status IN
                ('UNTRAINED_DEVELOPMENT_ONLY','RESEARCH_ONLY',
                 'PRODUCTION_PROMOTED'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_layers_source_product
  ON satellite_layers(source_product_id);
CREATE INDEX IF NOT EXISTS idx_layers_run ON satellite_layers(run_id);
CREATE INDEX IF NOT EXISTS idx_layers_model ON satellite_layers(model_version);
CREATE INDEX IF NOT EXISTS idx_layers_observation
  ON satellite_layers(observation_date DESC);
CREATE INDEX IF NOT EXISTS idx_layers_created ON satellite_layers(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_layers_data_class ON satellite_layers(data_class);

-- =====================================================================
-- 5. Provenance columns on satellite_changes
-- =====================================================================
ALTER TABLE satellite_changes
  ADD COLUMN IF NOT EXISTS run_id UUID,
  ADD COLUMN IF NOT EXISTS prev_layer_id BIGINT
    REFERENCES satellite_layers(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS new_layer_id BIGINT
    REFERENCES satellite_layers(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS prev_product_id BIGINT
    REFERENCES satellite_products(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS new_product_id BIGINT
    REFERENCES satellite_products(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS prev_observation_date DATE,
  ADD COLUMN IF NOT EXISTS new_observation_date DATE,
  ADD COLUMN IF NOT EXISTS model_version VARCHAR(50),
  ADD COLUMN IF NOT EXISTS preprocessing_version VARCHAR(50),
  ADD COLUMN IF NOT EXISTS data_class VARCHAR(20) NOT NULL DEFAULT 'derived';

-- area_sqm was INT; real polygon areas are fractional and can exceed INT range
-- for large regions. Widening is lossless.
ALTER TABLE satellite_changes
  ALTER COLUMN area_sqm TYPE DOUBLE PRECISION;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'chk_changes_data_class') THEN
    ALTER TABLE satellite_changes
      ADD CONSTRAINT chk_changes_data_class
      CHECK (data_class IN ('observed','derived','synthetic','test'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_changes_run ON satellite_changes(run_id);
CREATE INDEX IF NOT EXISTS idx_changes_created
  ON satellite_changes(created_at DESC);

-- =====================================================================
-- 6. Truthful ingestion log semantics
--    The old CHECK allowed only ('success','failed','skipped','processing'),
--    which forced the pipeline to write 'success' after a metadata-only
--    catalogue query. The new vocabulary distinguishes each real stage.
-- =====================================================================
ALTER TABLE satellite_ingest_log
  ADD COLUMN IF NOT EXISTS run_id UUID,
  ADD COLUMN IF NOT EXISTS product_id BIGINT
    REFERENCES satellite_products(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS stac_id VARCHAR(255),
  ADD COLUMN IF NOT EXISTS observation_date DATE,
  ADD COLUMN IF NOT EXISTS bytes_downloaded BIGINT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS duration_seconds DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS failure_class VARCHAR(50),
  ADD COLUMN IF NOT EXISTS retry_count INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS model_version VARCHAR(50),
  ADD COLUMN IF NOT EXISTS preprocessing_version VARCHAR(50);

-- Phase C fix (defect 1): ensure bytes_downloaded carries a real
-- server-side default even if the column already existed (e.g. created by
-- Base.metadata.create_all() with only a client-side/ORM default, which does
-- NOT appear in the generated DDL). ADD COLUMN IF NOT EXISTS above is a no-op
-- when the ORM created the column first, so the DEFAULT clause there never
-- actually reaches an ORM-first-bootstrapped database. This explicit
-- ALTER COLUMN SET DEFAULT runs unconditionally and is idempotent.
ALTER TABLE satellite_ingest_log
  ALTER COLUMN bytes_downloaded SET DEFAULT 0;
ALTER TABLE satellite_processing_runs
  ALTER COLUMN bytes_downloaded SET DEFAULT 0;
-- retry_count has the identical client-side-only-default gap, found via this
-- migration's own regression test (tests/integration/test_defect_regressions.py).
ALTER TABLE satellite_ingest_log
  ALTER COLUMN retry_count SET DEFAULT 0;

ALTER TABLE satellite_ingest_log
  ALTER COLUMN file_size_bytes TYPE BIGINT;

ALTER TABLE satellite_ingest_log DROP CONSTRAINT IF EXISTS valid_status;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'chk_ingest_status') THEN
    ALTER TABLE satellite_ingest_log
      ADD CONSTRAINT chk_ingest_status
      CHECK (ingestion_status IN (
        'discovered',
        'download_pending',
        'downloaded',
        'download_failed',
        'preprocessing',
        'preprocessed',
        'preprocessing_failed',
        'classification_pending',
        'classified',
        'classification_failed',
        'skipped_cloud',
        'skipped_no_credentials',
        'skipped_model_not_promoted',
        'failed',
        'validated',
        -- retained so pre-existing rows written under the old vocabulary
        -- remain insertable/updatable; new code never emits these.
        'success', 'skipped', 'processing'
      ));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_ingest_run ON satellite_ingest_log(run_id);
CREATE INDEX IF NOT EXISTS idx_ingest_product ON satellite_ingest_log(product_id);
CREATE INDEX IF NOT EXISTS idx_ingest_failure
  ON satellite_ingest_log(failure_class);

-- =====================================================================
-- 7. Planet imagery provenance — distinguish real from unavailable
-- =====================================================================
ALTER TABLE planet_imagery
  ADD COLUMN IF NOT EXISTS data_class VARCHAR(20) NOT NULL DEFAULT 'observed',
  ADD COLUMN IF NOT EXISTS source_api VARCHAR(50),
  ADD COLUMN IF NOT EXISTS retrieved_at TIMESTAMP;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'chk_planet_data_class') THEN
    ALTER TABLE planet_imagery
      ADD CONSTRAINT chk_planet_data_class
      CHECK (data_class IN ('observed','derived','synthetic','test'));
  END IF;
END $$;

-- =====================================================================
-- 8. Validation workflow provenance
-- =====================================================================
ALTER TABLE satellite_validations
  ADD COLUMN IF NOT EXISTS validated_by VARCHAR(100),
  ADD COLUMN IF NOT EXISTS unavailable_reason TEXT;

DO $$
BEGIN
  ALTER TABLE satellite_validations
    DROP CONSTRAINT IF EXISTS valid_validation_status;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'chk_validation_status') THEN
    ALTER TABLE satellite_validations
      ADD CONSTRAINT chk_validation_status
      CHECK (validation_status IN
        ('pending','confirmed','rejected','uncertain','unavailable','manual'));
  END IF;

  ALTER TABLE satellite_validations
    DROP CONSTRAINT IF EXISTS valid_validation_source;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'chk_validation_source') THEN
    ALTER TABLE satellite_validations
      ADD CONSTRAINT chk_validation_source
      CHECK (validation_source IS NULL OR validation_source IN
        ('planet_labs','manual','scraper_photo','field_survey','unavailable'));
  END IF;
END $$;

-- =====================================================================
-- 9. Label the existing synthetic `properties` rows for what they are.
--    worker/tasks.py generated these with random.uniform() over an HCMC
--    bounding box. They are NOT observed real-estate records. The table is
--    preserved (no deletion of historical data) but is now self-describing.
--
--    Phase C fix (defect 2): guarded with an existence check. `properties`
--    is a legacy table from the retired worker/db.py::ensure_schema() /
--    ops/init_db.sql bootstrap paths -- it does not exist on a fresh
--    canonical deployment (confirmed: routes/tiles.py's use of the string
--    'properties' is only an MVT layer-name label passed to ST_AsMVT, not a
--    reference to this table; the route queries FROM listings). On a
--    deployment where `properties` genuinely exists from an old bootstrap,
--    this section still runs and correctly labels its synthetic rows.
-- =====================================================================
DO $$
BEGIN
  IF to_regclass('public.properties') IS NOT NULL THEN
    ALTER TABLE properties
      ADD COLUMN IF NOT EXISTS data_class VARCHAR(20) NOT NULL DEFAULT 'synthetic',
      ADD COLUMN IF NOT EXISTS source VARCHAR(50);

    UPDATE properties
       SET data_class = 'synthetic',
           source = COALESCE(source, 'worker.tasks.random_property')
     WHERE source IS NULL;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_properties_data_class') THEN
      ALTER TABLE properties
        ADD CONSTRAINT chk_properties_data_class
        CHECK (data_class IN ('observed','derived','synthetic','test'));
    END IF;

    COMMENT ON TABLE properties IS
      'LEGACY / SYNTHETIC. Populated by worker/tasks.py using random.uniform() '
      'over a Ho Chi Minh City bounding box. Retained for history only. The '
      'operational, real-data table is public.listings. Do not surface rows '
      'from this table as observed market data.';
  END IF;
END $$;

INSERT INTO schema_migrations(version, description)
VALUES ('003',
        'Satellite product/asset/run provenance, truthful ingest statuses, '
        'data-class governance')
ON CONFLICT (version) DO NOTHING;

COMMIT;
