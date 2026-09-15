-- Migration 005: Extend planning_zones with Vietnamese zoning data schema
-- Applies: 2026-08-15
-- Reversible: Yes
-- Requires: 004_create_planning_zones_base.sql (creates the planning_zones table)
--
-- Phase C fix (2026-08-27, DAT.AI Phase C canonical recovery, additional
-- finding beyond the 3 assigned defects): this migration used unguarded
-- ADD COLUMN / CREATE INDEX statements, written for a migrations-only
-- bootstrap order. Since the current ORM model (app/models/zoning.py
-- PlanningZone) already defines every one of these columns, an ORM-first
-- bootstrap (Base.metadata.create_all(), which the live application
-- actually uses) creates them all up front -- causing this migration to
-- fail with "column already exists" the same way retired migration 001
-- failed. Same root cause class, same fix: add IF NOT EXISTS guards so the
-- migration is safe regardless of bootstrap order. See
-- DATAI_DEFECT_REPAIR_EVIDENCE.md for the full evidence chain.

BEGIN;

-- Add columns to planning_zones table
ALTER TABLE planning_zones
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(100) UNIQUE,
  ADD COLUMN IF NOT EXISTS project_name VARCHAR(500),
  ADD COLUMN IF NOT EXISTS zone_category VARCHAR(100),
  ADD COLUMN IF NOT EXISTS sub_categories JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS administrative_code VARCHAR(50),
  ADD COLUMN IF NOT EXISTS source_url TEXT,
  ADD COLUMN IF NOT EXISTS data_confidence FLOAT DEFAULT 0.95,
  ADD COLUMN IF NOT EXISTS ingestion_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS validation_status VARCHAR(50) DEFAULT 'ingested';

-- Add indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_planning_zones_project_id ON planning_zones(project_id);
CREATE INDEX IF NOT EXISTS idx_planning_zones_zone_category ON planning_zones(zone_category);
CREATE INDEX IF NOT EXISTS idx_planning_zones_admin_code ON planning_zones(administrative_code);
CREATE INDEX IF NOT EXISTS idx_planning_zones_validation ON planning_zones(validation_status);

-- Add comment documenting the schema.
--
-- Phase C provenance correction (defect/finding, see
-- DATAI_PROVENANCE_VERIFICATION.md): the original comment text asserted
-- "0.95 ... DVHC validated" as if this were a verified, per-record quality
-- measurement. Traced to the actual ingestion code
-- (worker/tasks/ingest_zoning_data.py), 0.95 is a flat constant applied to
-- every row in a batch (a CLI-argument default), not a computed or
-- independently verified per-record confidence score. The comment is
-- corrected here to describe what the column actually is: a declared
-- source-confidence value, not a verified measurement.
COMMENT ON TABLE planning_zones IS 'Zoning and land-use boundaries ingested from government planning-database exports. See data_confidence column comment for what the confidence value does and does not represent.';
COMMENT ON COLUMN planning_zones.data_confidence IS 'DECLARED_SOURCE_CONFIDENCE: a flat value supplied per ingestion batch (default 0.95), NOT a per-record computed or independently verified quality score. Every zone ingested in the same batch receives this identical value regardless of that zone''s individual data quality. See DATAI_PROVENANCE_VERIFICATION.md.';

INSERT INTO schema_migrations(version, description)
VALUES ('005', 'Extend planning_zones with Vietnamese zoning data schema (idempotent, Phase C)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
